import SwiftUI
import SwiftData
import ActivityKit
import AVFoundation

struct SessionView: View {
    @EnvironmentObject var authService: AuthService
    @EnvironmentObject var syncService: SyncService
    @Environment(\.modelContext) private var modelContext
    @Environment(\.dismiss) private var dismiss

    let classPeriod: ClassPeriod
    let students: [Student]

    @State private var session: LocalSession?
    @State private var sessionEvents: [LocalEvent] = []
    @State private var pendingEvents: [PendingEvent] = []
    @State private var showManualAdd = false
    @State private var showSummary = false
    @State private var elapsedSeconds: Int = 0
    @State private var timer: Timer?
    @State private var whisperService: WhisperService?
    @State private var isListening = false
    @State private var liveActivity: Activity<BehaviorActivityAttributes>?
    @State private var selectedTallyStudent: TallyStudentWrapper?
    @State private var showNameTraining = false
    @Query private var allAliases: [NameAlias]

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                // Header
                sessionHeader

                Divider()

                ScrollView {
                    VStack(spacing: 16) {
                        // Pending STT events
                        if !pendingEvents.isEmpty {
                            pendingSection
                        }

                        // Session tally
                        tallySection

                        // Last transcript
                        if let transcript = whisperService?.lastTranscript, !transcript.isEmpty {
                            HStack {
                                Image(systemName: "waveform")
                                    .foregroundStyle(.secondary)
                                Text("\"\(transcript)\"")
                                    .font(.caption)
                                    .foregroundStyle(.secondary)
                                    .italic()
                            }
                            .padding(.horizontal)
                        }
                    }
                    .padding(.vertical)
                }

                Divider()

                // Bottom controls
                HStack(spacing: 16) {
                    Button {
                        toggleListening()
                    } label: {
                        Label(
                            isListening ? "Pause" : "Listen",
                            systemImage: isListening ? "pause.fill" : "mic.fill"
                        )
                    }
                    .buttonStyle(.bordered)
                    .tint(isListening ? .orange : .blue)

                    Button {
                        showManualAdd = true
                    } label: {
                        Label("Add", systemImage: "plus")
                    }
                    .buttonStyle(.bordered)

                    Spacer()

                    Button(role: .destructive) {
                        endSession()
                    } label: {
                        Label("End", systemImage: "stop.fill")
                    }
                    .buttonStyle(.borderedProminent)
                    .tint(.red)
                }
                .padding()
            }
            .navigationBarTitleDisplayMode(.inline)
            .toolbar(.hidden, for: .navigationBar)
            .sheet(isPresented: $showManualAdd) {
                ManualAddSheet(
                    students: students,
                    onAdd: { studentId, studentName, eventType, note in
                        addManualEvent(
                            studentId: studentId,
                            studentName: studentName,
                            type: eventType,
                            note: note
                        )
                    }
                )
                .presentationDetents([.medium])
            }
            .sheet(isPresented: $showSummary) {
                SessionSummaryView(events: sessionEvents)
                    .onDisappear { dismiss() }
            }
            .sheet(isPresented: $showNameTraining) {
                if let whisperService {
                    NameTrainingView(
                        students: students,
                        whisperService: whisperService
                    )
                    .presentationDetents([.large])
                }
            }
            .sheet(item: $selectedTallyStudent) { wrapper in
                StudentEventsSheet(
                    studentName: wrapper.name,
                    events: sessionEvents.filter { $0.studentName == wrapper.name },
                    onDelete: { event in
                        deleteEvent(event)
                    }
                )
                .presentationDetents([.medium])
            }
            .onAppear { startSession() }
            .onDisappear { stopTimer() }
        }
    }

    // MARK: - Header

    private var sessionHeader: some View {
        HStack {
            VStack(alignment: .leading, spacing: 2) {
                Text(classPeriod.name)
                    .font(.headline)
                Text(formattedElapsed)
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .monospacedDigit()
            }

            Spacer()

            HStack(spacing: 8) {
                Button {
                    showNameTraining = true
                } label: {
                    Image(systemName: "waveform.and.person.filled")
                        .font(.subheadline)
                }
                .buttonStyle(.bordered)
                .controlSize(.small)

                if isListening {
                    Image(systemName: "mic.fill")
                        .foregroundStyle(.green)
                        .symbolEffect(.pulse)
                }

                Text("LIVE")
                    .font(.caption.bold())
                    .foregroundStyle(.white)
                    .padding(.horizontal, 8)
                    .padding(.vertical, 4)
                    .background(Capsule().fill(.red))
            }
        }
        .padding()
    }

    // MARK: - Pending Section

    private var pendingSection: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Pending (\(pendingEvents.count))")
                .font(.subheadline.bold())
                .foregroundStyle(.orange)
                .padding(.horizontal)

            ForEach($pendingEvents) { $pending in
                PendingEventCard(
                    event: $pending,
                    onApprove: { approvePending(pending) },
                    onSwitch: { switchPending(pending) },
                    onDismiss: { dismissPending(pending) }
                )
                .padding(.horizontal)
            }
        }
    }

    // MARK: - Tally Section

    private var tallySection: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Session Tally")
                .font(.subheadline.bold())
                .padding(.horizontal)

            if tallies.isEmpty {
                Text("No events yet")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 24)
            } else {
                ForEach(tallies, id: \.name) { tally in
                    StudentTallyRow(
                        name: tally.name,
                        corrections: tally.corrections,
                        praise: tally.praise,
                        onAddCorrection: {
                            addManualEvent(
                                studentId: tally.studentId,
                                studentName: tally.name,
                                type: .correction
                            )
                        },
                        onAddPraise: {
                            addManualEvent(
                                studentId: tally.studentId,
                                studentName: tally.name,
                                type: .praise
                            )
                        }
                    )
                    .contentShape(Rectangle())
                    .onTapGesture {
                        selectedTallyStudent = TallyStudentWrapper(name: tally.name)
                    }
                    .padding(.horizontal)
                }
            }
        }
    }

    // MARK: - Computed

    private var formattedElapsed: String {
        let minutes = elapsedSeconds / 60
        let seconds = elapsedSeconds % 60
        return String(format: "%d:%02d elapsed", minutes, seconds)
    }

    private struct TallyEntry {
        let name: String
        let studentId: UUID?
        let corrections: Int
        let praise: Int
    }

    private var tallies: [TallyEntry] {
        var dict: [String: (id: UUID?, corrections: Int, praise: Int)] = [:]
        for event in sessionEvents {
            var entry = dict[event.studentName] ?? (id: event.studentId, corrections: 0, praise: 0)
            if event.type == .correction {
                entry.corrections += 1
            } else {
                entry.praise += 1
            }
            dict[event.studentName] = entry
        }
        return dict.map { TallyEntry(name: $0.key, studentId: $0.value.id, corrections: $0.value.corrections, praise: $0.value.praise) }
            .sorted { $0.corrections > $1.corrections }
    }

    // MARK: - Actions

    private func startSession() {
        let newSession = LocalSession(
            classId: classPeriod.id,
            period: classPeriod.name
        )
        modelContext.insert(newSession)
        session = newSession

        // Start timer
        timer = Timer.scheduledTimer(withTimeInterval: 1, repeats: true) { _ in
            elapsedSeconds += 1
            // Update Live Activity elapsed time every minute
            if elapsedSeconds % 60 == 0 {
                updateLiveActivity()
            }
        }

        // Sync session to Supabase
        Task {
            guard let userId = authService.userId else { return }
            do {
                try await syncService.syncSession(newSession, teacherId: userId)
            } catch {
                // Will retry later
            }
        }

        // Start Live Activity
        startLiveActivity()

        // Init whisper with learned aliases
        var aliasMap: [UUID: [String]] = [:]
        for alias in allAliases {
            aliasMap[alias.studentId, default: []].append(alias.variant)
        }
        whisperService = WhisperService(students: students, aliases: aliasMap)
        whisperService?.onDetection = { detection in
            let pending = PendingEvent(
                id: UUID(),
                studentId: detection.studentId,
                studentName: detection.studentName,
                type: detection.type,
                transcript: detection.transcript,
                audioClipPath: detection.audioClipPath
            )
            pendingEvents.append(pending)
            // Haptic feedback
            UIImpactFeedbackGenerator(style: .medium).impactOccurred()
        }
    }

    private func toggleListening() {
        guard let whisperService else { return }
        if isListening {
            whisperService.stopListening()
            isListening = false
        } else {
            Task {
                do {
                    try await whisperService.loadModelIfNeeded()
                    await whisperService.startListening()
                    isListening = true
                } catch {
                    // Show error
                }
            }
        }
    }

    private func addManualEvent(
        studentId: UUID? = nil,
        studentName: String,
        type: EventType,
        note: String? = nil,
        audioClipPath: String? = nil
    ) {
        guard let session else { return }

        let event = LocalEvent(
            studentId: studentId,
            studentName: studentName,
            type: type,
            source: audioClipPath != nil ? .stt : .manual,
            note: note,
            audioClipPath: audioClipPath
        )
        event.session = session
        modelContext.insert(event)
        sessionEvents.append(event)

        // Update Live Activity
        updateLiveActivity(lastStudentName: studentName, lastEventType: type)

        // Sync to Supabase
        Task {
            guard let userId = authService.userId,
                  let remoteSessionId = session.remoteId else { return }
            do {
                try await syncService.syncEvent(event, sessionRemoteId: remoteSessionId, teacherId: userId)
            } catch {
                // Will retry
            }
        }
    }

    private func approvePending(_ pending: PendingEvent) {
        // Combine transcript with teacher's context note
        var note = pending.transcript
        if !pending.contextNote.isEmpty {
            note += " | Context: " + pending.contextNote
        }
        addManualEvent(
            studentId: pending.studentId,
            studentName: pending.studentName,
            type: pending.type,
            note: note,
            audioClipPath: pending.audioClipPath
        )
        pendingEvents.removeAll { $0.id == pending.id }
    }

    private func switchPending(_ pending: PendingEvent) {
        if let index = pendingEvents.firstIndex(where: { $0.id == pending.id }) {
            pendingEvents[index].type = pending.type == .correction ? .praise : .correction
        }
    }

    private func dismissPending(_ pending: PendingEvent) {
        // Clean up audio clip file
        if let path = pending.audioClipPath {
            try? FileManager.default.removeItem(atPath: path)
        }
        pendingEvents.removeAll { $0.id == pending.id }
    }

    private func deleteEvent(_ event: LocalEvent) {
        // Clean up audio clip file
        if let path = event.audioClipPath {
            try? FileManager.default.removeItem(atPath: path)
        }

        // Remove from local list
        sessionEvents.removeAll { $0.id == event.id }

        // Delete from SwiftData
        modelContext.delete(event)

        // Delete from Supabase
        Task {
            do {
                try await syncService.deleteEvent(event)
            } catch {
                // Local delete already done — remote will be orphaned but harmless
            }
        }

        // Update Live Activity
        updateLiveActivity()
    }

    private func endSession() {
        guard let session else { return }

        session.endedAt = .now
        session.isActive = false

        whisperService?.stopListening()
        isListening = false
        stopTimer()
        endLiveActivity()

        // Sync end
        Task {
            guard let userId = authService.userId else { return }
            do {
                try await syncService.endSession(session, teacherId: userId)
            } catch {
                // Queued for later
            }
        }

        showSummary = true
    }

    private func stopTimer() {
        timer?.invalidate()
        timer = nil
    }

    // MARK: - Live Activity

    private func startLiveActivity() {
        guard ActivityAuthorizationInfo().areActivitiesEnabled else { return }

        let attributes = BehaviorActivityAttributes(
            period: classPeriod.name,
            startTime: .now
        )
        let initialState = BehaviorActivityAttributes.ContentState(
            totalCorrections: 0,
            totalPraise: 0,
            lastStudentName: nil,
            lastEventType: nil,
            elapsedMinutes: 0
        )

        do {
            liveActivity = try Activity.request(
                attributes: attributes,
                content: .init(state: initialState, staleDate: nil)
            )
        } catch {
            // Live Activity not critical — session continues without it
        }
    }

    private func updateLiveActivity(lastStudentName: String? = nil, lastEventType: EventType? = nil) {
        guard let liveActivity else { return }

        let corrections = sessionEvents.filter { $0.type == .correction }.count
        let praise = sessionEvents.filter { $0.type == .praise }.count

        let state = BehaviorActivityAttributes.ContentState(
            totalCorrections: corrections,
            totalPraise: praise,
            lastStudentName: lastStudentName,
            lastEventType: lastEventType?.rawValue,
            elapsedMinutes: elapsedSeconds / 60
        )

        Task {
            await liveActivity.update(.init(state: state, staleDate: nil))
        }
    }

    private func endLiveActivity() {
        guard let liveActivity else { return }

        let corrections = sessionEvents.filter { $0.type == .correction }.count
        let praise = sessionEvents.filter { $0.type == .praise }.count

        let finalState = BehaviorActivityAttributes.ContentState(
            totalCorrections: corrections,
            totalPraise: praise,
            lastStudentName: nil,
            lastEventType: nil,
            elapsedMinutes: elapsedSeconds / 60
        )

        Task {
            await liveActivity.end(.init(state: finalState, staleDate: nil), dismissalPolicy: .after(.now + 60))
        }
    }
}

// MARK: - Pending Event Model

struct PendingEvent: Identifiable {
    let id: UUID
    let studentId: UUID?
    let studentName: String
    var type: EventType
    let transcript: String
    let audioClipPath: String?
    var contextNote: String = ""
}

// MARK: - Pending Event Card

struct PendingEventCard: View {
    @Binding var event: PendingEvent
    let onApprove: () -> Void
    let onSwitch: () -> Void
    let onDismiss: () -> Void

    @State private var audioPlayer: AVAudioPlayer?

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Text(event.studentName)
                    .font(.subheadline.bold())

                Text(event.type == .correction ? "correction" : "praise")
                    .font(.caption)
                    .foregroundStyle(event.type == .correction ? .red : .green)
                    .padding(.horizontal, 6)
                    .padding(.vertical, 2)
                    .background(
                        Capsule().fill(event.type == .correction ? Color.red.opacity(0.1) : Color.green.opacity(0.1))
                    )

                Spacer()

                if event.audioClipPath != nil {
                    Button {
                        playAudio()
                    } label: {
                        Image(systemName: "play.circle.fill")
                            .font(.title3)
                            .foregroundStyle(.blue)
                    }
                    .buttonStyle(.plain)
                }
            }

            Text("\"\(event.transcript)\"")
                .font(.caption)
                .foregroundStyle(.secondary)
                .italic()
                .lineLimit(3)

            // Context note — teacher adds detail before approving
            TextField("Add context (e.g. throwing paper at Jordan)", text: $event.contextNote)
                .font(.caption)
                .textFieldStyle(.roundedBorder)

            HStack(spacing: 12) {
                Button("Approve", action: onApprove)
                    .buttonStyle(.borderedProminent)
                    .tint(.green)
                    .controlSize(.small)

                Button(action: onSwitch) {
                    Image(systemName: "arrow.left.arrow.right")
                }
                .buttonStyle(.bordered)
                .controlSize(.small)

                Button(action: onDismiss) {
                    Image(systemName: "xmark")
                }
                .buttonStyle(.bordered)
                .tint(.red)
                .controlSize(.small)
            }
        }
        .padding()
        .background(
            RoundedRectangle(cornerRadius: 10)
                .fill(Color.orange.opacity(0.08))
        )
        .overlay(
            RoundedRectangle(cornerRadius: 10)
                .stroke(Color.orange.opacity(0.3), lineWidth: 1)
        )
    }

    private func playAudio() {
        guard let path = event.audioClipPath else { return }
        let url = URL(fileURLWithPath: path)
        try? AVAudioSession.sharedInstance().setCategory(.playback, mode: .default)
        try? AVAudioSession.sharedInstance().setActive(true)
        audioPlayer = try? AVAudioPlayer(contentsOf: url)
        audioPlayer?.play()
    }
}

// MARK: - Manual Add Sheet

struct ManualAddSheet: View {
    let students: [Student]
    let onAdd: (UUID?, String, EventType, String?) -> Void

    @Environment(\.dismiss) private var dismiss
    @State private var searchText = ""
    @State private var selectedStudent: Student?
    @State private var eventType: EventType = .correction
    @State private var note = ""

    private var filteredStudents: [Student] {
        if searchText.isEmpty { return students }
        return students.filter {
            $0.displayName.localizedCaseInsensitiveContains(searchText)
        }
    }

    var body: some View {
        NavigationStack {
            VStack(spacing: 16) {
                // Student search
                TextField("Search student...", text: $searchText)
                    .textFieldStyle(.roundedBorder)
                    .padding(.horizontal)

                if selectedStudent == nil {
                    List(filteredStudents) { student in
                        Button {
                            selectedStudent = student
                            searchText = student.displayName
                        } label: {
                            Text(student.displayName)
                        }
                    }
                    .listStyle(.plain)
                } else {
                    VStack(spacing: 16) {
                        // Type picker
                        Picker("Type", selection: $eventType) {
                            Text("Correction").tag(EventType.correction)
                            Text("Praise").tag(EventType.praise)
                        }
                        .pickerStyle(.segmented)
                        .padding(.horizontal)

                        // Note
                        TextField("Note (optional)", text: $note)
                            .textFieldStyle(.roundedBorder)
                            .padding(.horizontal)

                        // Add button
                        Button {
                            onAdd(
                                selectedStudent?.id,
                                selectedStudent?.displayName ?? searchText,
                                eventType,
                                note.isEmpty ? nil : note
                            )
                            dismiss()
                        } label: {
                            Text("Add Event")
                                .fontWeight(.semibold)
                                .frame(maxWidth: .infinity)
                                .frame(height: 44)
                        }
                        .buttonStyle(.borderedProminent)
                        .padding(.horizontal)

                        Spacer()
                    }
                }
            }
            .navigationTitle("Manual Add")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
            }
        }
    }
}

// MARK: - Tally Student Wrapper (for sheet binding)

struct TallyStudentWrapper: Identifiable {
    let id = UUID()
    let name: String
}

// MARK: - Student Events Sheet

struct StudentEventsSheet: View {
    let studentName: String
    let events: [LocalEvent]
    let onDelete: (LocalEvent) -> Void

    @Environment(\.dismiss) private var dismiss
    @State private var audioPlayer: AVAudioPlayer?

    var body: some View {
        NavigationStack {
            List {
                ForEach(events) { event in
                    HStack {
                        Image(systemName: event.type == .correction ? "minus.circle.fill" : "plus.circle.fill")
                            .foregroundStyle(event.type == .correction ? .red : .green)

                        VStack(alignment: .leading, spacing: 2) {
                            Text(event.type == .correction ? "Correction" : "Praise")
                                .font(.subheadline.bold())

                            if let note = event.note, !note.isEmpty {
                                Text(note)
                                    .font(.caption)
                                    .foregroundStyle(.secondary)
                            }

                            Text(event.eventTime, format: .dateTime.month(.abbreviated).day().hour().minute())
                                .font(.caption2)
                                .foregroundStyle(.tertiary)
                        }

                        Spacer()

                        if event.audioClipPath != nil {
                            Button {
                                playAudio(for: event)
                            } label: {
                                Image(systemName: "play.circle.fill")
                                    .font(.title3)
                                    .foregroundStyle(.blue)
                            }
                            .buttonStyle(.plain)
                        }

                        if event.syncStatus == .synced {
                            Image(systemName: "checkmark.icloud")
                                .font(.caption)
                                .foregroundStyle(.green)
                        }
                    }
                }
                .onDelete { offsets in
                    for index in offsets {
                        onDelete(events[index])
                    }
                    if events.count <= offsets.count {
                        dismiss()
                    }
                }
            }
            .navigationTitle(studentName)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    Button("Done") { dismiss() }
                }
            }
        }
    }

    private func playAudio(for event: LocalEvent) {
        guard let path = event.audioClipPath else { return }
        let url = URL(fileURLWithPath: path)
        try? AVAudioSession.sharedInstance().setCategory(.playback, mode: .default)
        try? AVAudioSession.sharedInstance().setActive(true)
        audioPlayer = try? AVAudioPlayer(contentsOf: url)
        audioPlayer?.play()
    }
}
