import Foundation
import AVFoundation
import WhisperKit

struct STTDetection {
    let studentId: UUID?
    let studentName: String
    let type: EventType
    let transcript: String
    let audioClipPath: String?
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
    private let aliases: [UUID: [String]]
    private var studentPatterns: [(Student, NSRegularExpression)] = []
    private var studentNamePrompt: String = ""

    // Rolling history for richer context on detections
    private var previousChunkAudio: [Float] = []
    private var transcriptHistory: [String] = []  // last N transcripts
    private let maxTranscriptHistory = 4

    // Adaptive voice gate — only emit detections when speaker is near the phone
    private var recentRMS: [Float] = []         // rolling window of chunk RMS values
    private let rmsWindowSize = 12              // ~60s of history at 5s chunks
    private let proximityMultiplier: Float = 2.0 // current chunk must be 2x ambient

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

    init(students: [Student], aliases: [UUID: [String]] = [:]) {
        self.students = students
        self.aliases = aliases
        buildStudentPatterns()
        buildNamePrompt()
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
            try audioSession.setCategory(.record, mode: .default)
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

            // Process every 5 seconds for more context per chunk
            processingTimer = Timer.scheduledTimer(withTimeInterval: 5.0, repeats: true) { [weak self] _ in
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
        overlapBuffer = []
        previousChunkAudio = []
        transcriptHistory = []
        recentRMS = []
        isListening = false
    }

    // MARK: - Audio Processing

    private var overlapBuffer: [Float] = []

    private func processAudioChunk() async {
        guard !audioBuffer.isEmpty else { return }

        // Prepend overlap from previous chunk to catch phrases that straddle boundaries
        let chunk = overlapBuffer + audioBuffer

        // Keep last 1.5s (24000 samples at 16kHz) for next chunk's overlap
        let overlapSamples = 24000
        if audioBuffer.count > overlapSamples {
            overlapBuffer = Array(audioBuffer.suffix(overlapSamples))
        } else {
            overlapBuffer = audioBuffer
        }
        audioBuffer = []

        // RMS silence check (low threshold to catch distant speech)
        let rms = sqrt(chunk.map { $0 * $0 }.reduce(0, +) / Float(chunk.count))
        guard rms > 0.003 else { return }

        // Track ambient volume for adaptive voice gate
        recentRMS.append(rms)
        if recentRMS.count > rmsWindowSize {
            recentRMS.removeFirst()
        }

        // Apply software gain to boost quieter audio
        let gain: Float = 2.0
        let amplified = chunk.map { min(max($0 * gain, -1.0), 1.0) }

        guard let whisperKit else { return }

        do {
            // Build decoding options with student name prompt tokens for bias
            var options = DecodingOptions()
            if !studentNamePrompt.isEmpty, let tokenizer = whisperKit.tokenizer {
                options.promptTokens = tokenizer.encode(text: studentNamePrompt)
            }

            let results = try await whisperKit.transcribe(audioArray: amplified, decodeOptions: options)
            guard let text = results.first?.text.trimmingCharacters(in: .whitespacesAndNewlines),
                  !text.isEmpty else { return }

            lastTranscript = text

            // Maintain rolling transcript history
            transcriptHistory.append(text)
            if transcriptHistory.count > maxTranscriptHistory {
                transcriptHistory.removeFirst()
            }

            // Detect student names in transcript
            // Check current + previous transcript for broader context matching
            let contextTranscript = transcriptHistory.joined(separator: " ")
            let detections = detectStudents(in: contextTranscript)

            // Voice gate: only emit detections if speaker is near the phone
            // Compare current chunk RMS against ambient baseline
            let isNearby: Bool = {
                guard recentRMS.count >= 3 else { return true } // not enough data yet, allow
                let sorted = recentRMS.sorted()
                let median = sorted[sorted.count / 2]
                // Must be louder than ambient median * multiplier
                return rms >= median * proximityMultiplier
            }()

            if !detections.isEmpty && isNearby {
                // Save extended audio: previous chunk + current chunk (~10s)
                let extendedAudio = previousChunkAudio + amplified
                let clipPath = saveAudioClip(extendedAudio)

                // Build rich transcript from history
                let richTranscript = transcriptHistory.joined(separator: " ")

                for detection in detections {
                    let withContext = STTDetection(
                        studentId: detection.studentId,
                        studentName: detection.studentName,
                        type: detection.type,
                        transcript: richTranscript,
                        audioClipPath: clipPath
                    )
                    onDetection?(withContext)
                }
            }

            // Store current chunk as previous for next iteration
            previousChunkAudio = amplified
        } catch {
            // Transcription failed, skip chunk
        }
    }

    // MARK: - Name Detection

    private func buildStudentPatterns() {
        studentPatterns = []
        for student in students {
            var patterns: [String] = []

            // Match first name, last name, full display name
            for name in [student.firstName, student.lastName, student.displayName] where name.count >= 3 {
                let escaped = NSRegularExpression.escapedPattern(for: name)
                patterns.append("\\b\(escaped)\\b")
            }

            // Match honorific + last name (Mr./Miss/Mrs./Ms. LastName)
            if student.lastName.count >= 3 {
                let escapedLast = NSRegularExpression.escapedPattern(for: student.lastName)
                patterns.append("\\b(?:mr|mrs|ms|miss|mister)\\.?\\s+\(escapedLast)\\b")
            }

            // Add learned alias patterns
            if let aliasVariants = aliases[student.id] {
                for variant in aliasVariants where variant.count >= 2 {
                    let escaped = NSRegularExpression.escapedPattern(for: variant)
                    patterns.append("\\b\(escaped)\\b")
                }
            }

            for pattern in patterns {
                if let regex = try? NSRegularExpression(
                    pattern: pattern,
                    options: .caseInsensitive
                ) {
                    studentPatterns.append((student, regex))
                }
            }
        }
    }

    private func buildNamePrompt() {
        let names = students.map { $0.displayName }
        guard !names.isEmpty else { return }
        studentNamePrompt = "Students: " + names.joined(separator: ", ") + "."
    }

    private func detectStudents(in text: String) -> [STTDetection] {
        let range = NSRange(text.startIndex..., in: text)
        var matched: Set<UUID> = []
        var detections: [STTDetection] = []

        // Phase 1: Exact regex matching (includes aliases)
        for (student, regex) in studentPatterns {
            guard !matched.contains(student.id) else { continue }
            if regex.firstMatch(in: text, range: range) != nil {
                matched.insert(student.id)
                let eventType = classify(text: text)
                detections.append(STTDetection(
                    studentId: student.id,
                    studentName: student.displayName,
                    type: eventType,
                    transcript: text,
                    audioClipPath: nil
                ))
            }
        }

        // Phase 2: Fuzzy matching for unmatched students
        let words = text.lowercased()
            .components(separatedBy: .whitespacesAndNewlines)
            .map { $0.trimmingCharacters(in: .punctuationCharacters) }
            .filter { $0.count >= 2 }

        for student in students where !matched.contains(student.id) {
            let namesToCheck = [student.firstName, student.lastName].filter { $0.count >= 2 }
            for name in namesToCheck {
                let nameLower = name.lowercased()
                let threshold = nameLower.count <= 4 ? 1 : 2
                let found = words.contains { word in
                    levenshteinDistance(word, nameLower) <= threshold
                }
                if found {
                    matched.insert(student.id)
                    let eventType = classify(text: text)
                    detections.append(STTDetection(
                        studentId: student.id,
                        studentName: student.displayName,
                        type: eventType,
                        transcript: text,
                        audioClipPath: nil
                    ))
                    break
                }
            }
        }

        return detections
    }

    // MARK: - Fuzzy Matching

    private func levenshteinDistance(_ a: String, _ b: String) -> Int {
        let aChars = Array(a)
        let bChars = Array(b)
        let aLen = aChars.count
        let bLen = bChars.count

        if aLen == 0 { return bLen }
        if bLen == 0 { return aLen }

        var prev = Array(0...bLen)
        var curr = [Int](repeating: 0, count: bLen + 1)

        for i in 1...aLen {
            curr[0] = i
            for j in 1...bLen {
                let cost = aChars[i - 1] == bChars[j - 1] ? 0 : 1
                curr[j] = min(
                    prev[j] + 1,       // deletion
                    curr[j - 1] + 1,   // insertion
                    prev[j - 1] + cost  // substitution
                )
            }
            prev = curr
        }

        return prev[bLen]
    }

    // MARK: - Audio Clip Cleanup

    /// Deletes audio clips older than 24 hours. Call on app launch or session start.
    static func cleanupOldClips() {
        let fm = FileManager.default
        let cutoff = Date.now.addingTimeInterval(-24 * 60 * 60)

        guard let files = try? fm.contentsOfDirectory(
            at: clipsDirectory,
            includingPropertiesForKeys: [.creationDateKey],
            options: .skipsHiddenFiles
        ) else { return }

        for file in files where file.pathExtension == "wav" {
            guard let attrs = try? fm.attributesOfItem(atPath: file.path),
                  let created = attrs[.creationDate] as? Date,
                  created < cutoff else { continue }
            try? fm.removeItem(at: file)
        }
    }

    // MARK: - Audio Clip Saving

    private static let clipsDirectory: URL = {
        let docs = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
        let dir = docs.appendingPathComponent("audio_clips", isDirectory: true)
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        return dir
    }()

    private func saveAudioClip(_ samples: [Float]) -> String? {
        let filename = UUID().uuidString + ".wav"
        let url = Self.clipsDirectory.appendingPathComponent(filename)

        guard let format = AVAudioFormat(
            commonFormat: .pcmFormatFloat32,
            sampleRate: 16000,
            channels: 1,
            interleaved: false
        ) else { return nil }

        guard let buffer = AVAudioPCMBuffer(
            pcmFormat: format,
            frameCapacity: AVAudioFrameCount(samples.count)
        ) else { return nil }

        buffer.frameLength = AVAudioFrameCount(samples.count)
        if let channelData = buffer.floatChannelData?[0] {
            for i in 0..<samples.count {
                channelData[i] = samples[i]
            }
        }

        do {
            let file = try AVAudioFile(forWriting: url, settings: format.settings)
            try file.write(from: buffer)
            return url.path
        } catch {
            return nil
        }
    }

    // MARK: - Name Training

    func transcribeAudioSamples(_ samples: [Float]) async -> String? {
        guard let whisperKit else { return nil }
        do {
            let results = try await whisperKit.transcribe(audioArray: samples)
            return results.first?.text.trimmingCharacters(in: .whitespacesAndNewlines)
        } catch {
            return nil
        }
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
