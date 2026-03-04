import Foundation
import AVFoundation
import WhisperKit

struct STTDetection {
    let studentId: UUID?
    let studentName: String
    let type: EventType
    let transcript: String
}

@MainActor
class WhisperService: ObservableObject {
    @Published var isModelLoaded = false
    @Published var isListening = false
    @Published var lastTranscript = ""
    @Published var modelLoadProgress: Double = 0

    var onDetection: ((STTDetection) -> Void)?

    private var whisperKit: WhisperKit?
    private var audioEngine: AVAudioEngine?
    private var audioBuffer: [Float] = []
    private var processingTimer: Timer?

    private let students: [Student]
    private var studentPatterns: [(Student, NSRegularExpression)] = []

    // Classification patterns (ported from web useBehaviorListener.js)
    private static let correctionPatterns: [NSRegularExpression] = {
        let patterns = [
            "\\bstop\\b", "\\bsit down\\b", "\\bfocus\\b",
            "\\bplease\\s+(quiet|listen|stop)\\b", "\\bi need you to\\b",
            "\\bdon'?t\\b", "\\bpay attention\\b", "\\bhands to yourself\\b",
            "\\bthat'?s enough\\b", "\\bwarning\\b", "\\bin your seat\\b",
            "\\bturn around\\b", "\\bput.+away\\b", "\\bno (talking|phones)\\b"
        ]
        return patterns.compactMap { try? NSRegularExpression(pattern: $0, options: .caseInsensitive) }
    }()

    private static let praisePatterns: [NSRegularExpression] = {
        let patterns = [
            "\\bgood job\\b", "\\bgreat (work|job)\\b", "\\bexcellent\\b",
            "\\bthank you\\b", "\\bwell done\\b", "\\bawesome\\b",
            "\\bnice (work|job)\\b", "\\bperfect\\b", "\\bi'?m proud\\b",
            "\\bway to go\\b", "\\bkeep it up\\b",
            "\\bgood (thinking|listening|behavior)\\b"
        ]
        return patterns.compactMap { try? NSRegularExpression(pattern: $0, options: .caseInsensitive) }
    }()

    init(students: [Student]) {
        self.students = students
        buildStudentPatterns()
    }

    // MARK: - Model Loading

    func loadModelIfNeeded() async throws {
        guard !isModelLoaded else { return }

        whisperKit = try await WhisperKit(
            model: "base",
            verbose: false
        )
        isModelLoaded = true
    }

    // MARK: - Audio Capture

    func startListening() async {
        guard isModelLoaded else { return }

        let audioSession = AVAudioSession.sharedInstance()
        do {
            try audioSession.setCategory(.record, mode: .measurement)
            try audioSession.setActive(true)
        } catch {
            return
        }

        audioEngine = AVAudioEngine()
        guard let audioEngine else { return }

        let inputNode = audioEngine.inputNode
        let format = inputNode.outputFormat(forBus: 0)

        // Target: 16kHz mono
        guard let targetFormat = AVAudioFormat(
            commonFormat: .pcmFormatFloat32,
            sampleRate: 16000,
            channels: 1,
            interleaved: false
        ) else { return }

        guard let converter = AVAudioConverter(from: format, to: targetFormat) else { return }

        inputNode.installTap(onBus: 0, bufferSize: 4096, format: format) { [weak self] buffer, _ in
            guard let self else { return }

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
                    self.audioBuffer.append(contentsOf: frames)
                }
            }
        }

        do {
            try audioEngine.start()
            isListening = true

            // Process every 3 seconds
            processingTimer = Timer.scheduledTimer(withTimeInterval: 3.0, repeats: true) { [weak self] _ in
                Task { @MainActor in
                    await self?.processAudioChunk()
                }
            }
        } catch {
            return
        }
    }

    func stopListening() {
        processingTimer?.invalidate()
        processingTimer = nil

        audioEngine?.inputNode.removeTap(onBus: 0)
        audioEngine?.stop()
        audioEngine = nil
        audioBuffer = []
        isListening = false
    }

    // MARK: - Audio Processing

    private func processAudioChunk() async {
        guard !audioBuffer.isEmpty else { return }

        let chunk = audioBuffer
        audioBuffer = []

        // RMS silence check
        let rms = sqrt(chunk.map { $0 * $0 }.reduce(0, +) / Float(chunk.count))
        guard rms > 0.01 else { return }

        guard let whisperKit else { return }

        do {
            let results = try await whisperKit.transcribe(audioArray: chunk)
            guard let text = results.first?.text.trimmingCharacters(in: .whitespacesAndNewlines),
                  !text.isEmpty else { return }

            lastTranscript = text

            // Detect student names in transcript
            let detections = detectStudents(in: text)
            for detection in detections {
                onDetection?(detection)
            }
        } catch {
            // Transcription failed, skip chunk
        }
    }

    // MARK: - Name Detection

    private func buildStudentPatterns() {
        studentPatterns = []
        for student in students {
            let names = Set([
                student.firstName,
                student.lastName,
                student.displayName
            ].filter { $0.count >= 3 })

            for name in names {
                let escaped = NSRegularExpression.escapedPattern(for: name)
                if let regex = try? NSRegularExpression(
                    pattern: "\\b\(escaped)\\b",
                    options: .caseInsensitive
                ) {
                    studentPatterns.append((student, regex))
                }
            }
        }
    }

    private func detectStudents(in text: String) -> [STTDetection] {
        let range = NSRange(text.startIndex..., in: text)
        var matched: Set<UUID> = []
        var detections: [STTDetection] = []

        for (student, regex) in studentPatterns {
            guard !matched.contains(student.id) else { continue }
            if regex.firstMatch(in: text, range: range) != nil {
                matched.insert(student.id)
                let eventType = classify(text: text)
                detections.append(STTDetection(
                    studentId: student.id,
                    studentName: student.displayName,
                    type: eventType,
                    transcript: text
                ))
            }
        }

        return detections
    }

    // MARK: - Classification

    private func classify(text: String) -> EventType {
        let range = NSRange(text.startIndex..., in: text)

        let praiseScore = Self.praisePatterns.filter {
            $0.firstMatch(in: text, range: range) != nil
        }.count

        let correctionScore = Self.correctionPatterns.filter {
            $0.firstMatch(in: text, range: range) != nil
        }.count

        if praiseScore > correctionScore {
            return .praise
        } else {
            return .correction
        }
    }
}
