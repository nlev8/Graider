import SwiftUI
import SwiftData
import ActivityKit

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

            ForEach(pendingEvents) { pending in
                PendingEventCard(
                    event: pending,
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

        // Init whisper
        whisperService = WhisperService(students: students)
        whisperService?.onDetection = { detection in
            let pending = PendingEvent(
                id: UUID(),
                studentId: detection.studentId,
                studentName: detection.studentName,
                type: detection.type,
                transcript: detection.transcript
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
        note: String? = nil
    ) {
        guard let session else { return }

        let event = LocalEvent(
            studentId: studentId,
            studentName: studentName,
            type: type,
            source: .manual,
            note: note
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
        addManualEvent(
            studentId: pending.studentId,
            studentName: pending.studentName,
            type: pending.type,
            note: pending.transcript
        )
        pendingEvents.removeAll { $0.id == pending.id }
    }

    private func switchPending(_ pending: PendingEvent) {
        if let index = pendingEvents.firstIndex(where: { $0.id == pending.id }) {
            pendingEvents[index].type = pending.type == .correction ? .praise : .correction
        }
    }

    private func dismissPending(_ pending: PendingEvent) {
        pendingEvents.removeAll { $0.id == pending.id }
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
}

// MARK: - Pending Event Card

struct PendingEventCard: View {
    let event: PendingEvent
    let onApprove: () -> Void
    let onSwitch: () -> Void
    let onDismiss: () -> Void

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
            }

            Text("\"\(event.transcript)\"")
                .font(.caption)
                .foregroundStyle(.secondary)
                .italic()

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
