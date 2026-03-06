import SwiftUI
import SwiftData
import AVFoundation

struct NameTrainingView: View {
    let students: [Student]
    let whisperService: WhisperService

    @Environment(\.modelContext) private var modelContext
    @Environment(\.dismiss) private var dismiss
    @Query private var allAliases: [NameAlias]

    @State private var recordingStudentId: UUID?
    @State private var audioEngine: AVAudioEngine?
    @State private var recordedSamples: [Float] = []
    @State private var isTranscribing = false
    @State private var lastResult: [UUID: String] = [:]
    @State private var synthesizer = AVSpeechSynthesizer()
    @State private var enhancedVoice: AVSpeechSynthesisVoice?

    var body: some View {
        NavigationStack {
            List {
                Section {
                    Text("Say each name to teach the app how you pronounce it. Record multiple times for better accuracy.")
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                }

                Section {
                    ForEach(students) { student in
                        studentRow(student)
                    }
                }
            }
            .navigationTitle("Train Names")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    Button("Done") { dismiss() }
                }
            }
        }
        .onAppear {
            // Find the best available enhanced English voice
            enhancedVoice = findBestVoice()
        }
        .onDisappear {
            stopRecording()
        }
    }

    // MARK: - Student Row

    @ViewBuilder
    private func studentRow(_ student: Student) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                VStack(alignment: .leading, spacing: 2) {
                    HStack(spacing: 6) {
                        if hasAlias(for: student.id) {
                            Image(systemName: "checkmark.circle.fill")
                                .foregroundStyle(.green)
                                .font(.subheadline)
                        }
                        Text(student.displayName)
                            .font(.body)
                    }

                    if let result = lastResult[student.id] {
                        Text("heard: \"\(result)\"")
                            .font(.caption)
                            .foregroundStyle(.orange)
                    }
                }

                Spacer()

                if isTranscribing && recordingStudentId == student.id {
                    ProgressView()
                        .controlSize(.small)
                } else {
                    // TTS playback button
                    Button {
                        speakName(student.displayName)
                    } label: {
                        Image(systemName: "speaker.wave.2.fill")
                            .font(.body)
                            .foregroundStyle(.secondary)
                    }
                    .buttonStyle(.plain)

                    // Record button
                    Button {
                        if recordingStudentId == student.id {
                            finishRecording(for: student)
                        } else {
                            startRecording(for: student)
                        }
                    } label: {
                        Image(systemName: recordingStudentId == student.id ? "stop.circle.fill" : "mic.circle.fill")
                            .font(.title2)
                            .foregroundStyle(recordingStudentId == student.id ? .red : .blue)
                    }
                    .buttonStyle(.plain)
                    .disabled(isTranscribing)
                }
            }

            // Show saved variants with delete
            let aliases = aliasesForStudent(student.id)
            if !aliases.isEmpty {
                FlowLayout(spacing: 6) {
                    ForEach(aliases) { alias in
                        HStack(spacing: 4) {
                            Text(alias.variant)
                                .font(.caption)
                            Button {
                                modelContext.delete(alias)
                            } label: {
                                Image(systemName: "xmark.circle.fill")
                                    .font(.caption2)
                                    .foregroundStyle(.secondary)
                            }
                            .buttonStyle(.plain)
                        }
                        .padding(.horizontal, 8)
                        .padding(.vertical, 3)
                        .background(Capsule().fill(Color.orange.opacity(0.15)))
                    }
                }
            }
        }
        .padding(.vertical, 2)
    }

    // MARK: - TTS

    private func findBestVoice() -> AVSpeechSynthesisVoice? {
        let voices = AVSpeechSynthesisVoice.speechVoices()
        let enVoices = voices.filter { $0.language.hasPrefix("en") }

        // Prefer enhanced quality voices
        if let enhanced = enVoices.first(where: { $0.quality == .enhanced }) {
            return enhanced
        }
        // Fall back to any en-US voice
        return AVSpeechSynthesisVoice(language: "en-US")
    }

    private func speakName(_ name: String) {
        synthesizer.stopSpeaking(at: .immediate)
        let utterance = AVSpeechUtterance(string: name)
        utterance.rate = AVSpeechUtteranceDefaultSpeechRate * 0.85
        utterance.pitchMultiplier = 1.05
        utterance.voice = enhancedVoice ?? AVSpeechSynthesisVoice(language: "en-US")

        try? AVAudioSession.sharedInstance().setCategory(.playback, mode: .default)
        try? AVAudioSession.sharedInstance().setActive(true)
        synthesizer.speak(utterance)
    }

    // MARK: - Alias Helpers

    private func hasAlias(for studentId: UUID) -> Bool {
        allAliases.contains { $0.studentId == studentId }
    }

    private func aliasesForStudent(_ studentId: UUID) -> [NameAlias] {
        allAliases.filter { $0.studentId == studentId }
    }

    // MARK: - Recording

    private func startRecording(for student: Student) {
        stopRecording()
        recordingStudentId = student.id
        recordedSamples = []

        let session = AVAudioSession.sharedInstance()
        do {
            try session.setCategory(.record, mode: .default)
            try session.setActive(true)
        } catch {
            recordingStudentId = nil
            return
        }

        audioEngine = AVAudioEngine()
        guard let engine = audioEngine else { return }

        let inputNode = engine.inputNode
        let format = inputNode.outputFormat(forBus: 0)

        guard let targetFormat = AVAudioFormat(
            commonFormat: .pcmFormatFloat32,
            sampleRate: 16000,
            channels: 1,
            interleaved: false
        ) else { return }

        guard let converter = AVAudioConverter(from: format, to: targetFormat) else { return }

        inputNode.installTap(onBus: 0, bufferSize: 4096, format: format) { [self] buffer, _ in
            let frameCount = AVAudioFrameCount(
                Double(buffer.frameLength) * 16000.0 / format.sampleRate
            )
            guard frameCount > 0 else { return }

            guard let convertedBuffer = AVAudioPCMBuffer(
                pcmFormat: targetFormat,
                frameCapacity: frameCount
            ) else { return }

            var error: NSError?
            converter.convert(to: convertedBuffer, error: &error) { _, outStatus in
                outStatus.pointee = .haveData
                return buffer
            }

            if let channelData = convertedBuffer.floatChannelData?[0] {
                let frames = Array(UnsafeBufferPointer(
                    start: channelData,
                    count: Int(convertedBuffer.frameLength)
                ))
                Task { @MainActor in
                    self.recordedSamples.append(contentsOf: frames)
                }
            }
        }

        do {
            try engine.start()
        } catch {
            recordingStudentId = nil
        }
    }

    private func stopRecording() {
        audioEngine?.inputNode.removeTap(onBus: 0)
        audioEngine?.stop()
        audioEngine = nil
    }

    private func finishRecording(for student: Student) {
        stopRecording()
        let samples = recordedSamples
        recordedSamples = []
        isTranscribing = true

        Task {
            defer {
                isTranscribing = false
                recordingStudentId = nil
            }

            guard !samples.isEmpty else { return }

            guard let transcription = await whisperService.transcribeAudioSamples(samples),
                  !transcription.isEmpty else { return }

            let cleaned = transcription.trimmingCharacters(in: .whitespacesAndNewlines)
                .trimmingCharacters(in: .punctuationCharacters)
            guard !cleaned.isEmpty else { return }

            let transcribed = cleaned.lowercased()
            lastResult[student.id] = cleaned

            // Check if it matches the actual name
            let matchesExact = transcribed == student.firstName.lowercased()
                || transcribed == student.lastName.lowercased()
                || transcribed == student.displayName.lowercased()

            guard !matchesExact else { return }

            // Check for duplicate variant (persisted + session)
            let alreadyExists = allAliases.contains {
                $0.studentId == student.id && $0.variant.lowercased() == transcribed
            }

            if !alreadyExists {
                let alias = NameAlias(studentId: student.id, variant: cleaned)
                modelContext.insert(alias)
            }
        }
    }
}

// MARK: - Flow Layout for variant chips

struct FlowLayout: Layout {
    var spacing: CGFloat = 6

    func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) -> CGSize {
        let maxWidth = proposal.width ?? .infinity
        var x: CGFloat = 0
        var y: CGFloat = 0
        var rowHeight: CGFloat = 0

        for subview in subviews {
            let size = subview.sizeThatFits(.unspecified)
            if x + size.width > maxWidth && x > 0 {
                x = 0
                y += rowHeight + spacing
                rowHeight = 0
            }
            x += size.width + spacing
            rowHeight = max(rowHeight, size.height)
        }

        return CGSize(width: maxWidth, height: y + rowHeight)
    }

    func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) {
        var x = bounds.minX
        var y = bounds.minY
        var rowHeight: CGFloat = 0

        for subview in subviews {
            let size = subview.sizeThatFits(.unspecified)
            if x + size.width > bounds.maxX && x > bounds.minX {
                x = bounds.minX
                y += rowHeight + spacing
                rowHeight = 0
            }
            subview.place(at: CGPoint(x: x, y: y), proposal: .unspecified)
            x += size.width + spacing
            rowHeight = max(rowHeight, size.height)
        }
    }
}
