import Foundation
import Supabase
import SwiftData
import Network

@MainActor
class SyncService: ObservableObject {
    @Published var isOnline = true
    @Published var isSyncing = false
    @Published var classes: [ClassPeriod] = []
    @Published var students: [Student] = []

    private let supabase: SupabaseManager
    private let monitor = NWPathMonitor()
    private let monitorQueue = DispatchQueue(label: "network-monitor")

    init(supabase: SupabaseManager) {
        self.supabase = supabase
        startNetworkMonitor()
    }

    // MARK: - Network Monitoring

    private func startNetworkMonitor() {
        monitor.pathUpdateHandler = { [weak self] path in
            Task { @MainActor in
                self?.isOnline = path.status == .satisfied
                if path.status == .satisfied {
                    // TODO: Flush pending sync queue
                }
            }
        }
        monitor.start(queue: monitorQueue)
    }

    // MARK: - Teacher Settings

    func fetchTeacherName() async throws -> String? {
        let session = try await supabase.client.auth.session
        let token = session.accessToken

        var request = URLRequest(url: URL(string: "https://app.graider.live/api/load-global-settings")!)
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")

        let (data, response) = try await URLSession.shared.data(for: request)
        let httpResp = response as? HTTPURLResponse
        let body = String(data: data, encoding: .utf8) ?? ""
        print("[SyncService] fetchTeacherName status=\(httpResp?.statusCode ?? -1) body=\(body.prefix(300))")

        guard httpResp?.statusCode == 200 else { return nil }

        // Parse flexibly — settings may have various shapes
        guard let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let settings = json["settings"] as? [String: Any] else {
            return nil
        }

        // teacher_name lives inside settings.config (web app structure)
        if let config = settings["config"] as? [String: Any],
           let name = config["teacher_name"] as? String, !name.isEmpty {
            return name
        }
        // Fallback: check top-level of settings
        if let name = settings["teacher_name"] as? String, !name.isEmpty {
            return name
        }
        return nil
    }

    // MARK: - Fetch Classes & Students

    func fetchClasses(teacherId: UUID) async throws {
        var response: [ClassPeriod] = try await supabase.client
            .from("classes")
            .select()
            .eq("teacher_id", value: teacherId.uuidString)
            .execute()
            .value

        // Compute student counts from junction table
        struct CountRow: Codable {
            let classId: UUID
            enum CodingKeys: String, CodingKey {
                case classId = "class_id"
            }
        }

        let classIds = response.map { $0.id.uuidString }
        if !classIds.isEmpty {
            let junctionRows: [CountRow] = try await supabase.client
                .from("class_students")
                .select("class_id")
                .in("class_id", values: classIds)
                .execute()
                .value

            var counts: [UUID: Int] = [:]
            for row in junctionRows {
                counts[row.classId, default: 0] += 1
            }

            for i in response.indices {
                response[i].studentCount = counts[response[i].id] ?? 0
            }
        }

        classes = response
    }

    func fetchStudents(classId: UUID) async throws -> [Student] {
        // Fetch student IDs from junction table, then student details
        struct ClassStudent: Codable {
            let studentId: UUID
            enum CodingKeys: String, CodingKey {
                case studentId = "student_id"
            }
        }

        let junctionRows: [ClassStudent] = try await supabase.client
            .from("class_students")
            .select("student_id")
            .eq("class_id", value: classId.uuidString)
            .execute()
            .value

        let studentIds = junctionRows.map { $0.studentId.uuidString }
        guard !studentIds.isEmpty else { return [] }

        let fetchedStudents: [Student] = try await supabase.client
            .from("students")
            .select()
            .in("id", values: studentIds)
            .eq("is_active", value: true)
            .execute()
            .value

        return fetchedStudents.sorted { $0.lastName < $1.lastName }
    }

    func fetchAllStudents(teacherId: UUID) async throws {
        let fetched: [Student] = try await supabase.client
            .from("students")
            .select()
            .eq("teacher_id", value: teacherId.uuidString)
            .eq("is_active", value: true)
            .execute()
            .value

        students = fetched.sorted { $0.lastName < $1.lastName }
    }

    // MARK: - Roster CRUD

    func createClass(name: String, subject: String?, gradeLevel: String?, teacherId: UUID) async throws -> ClassPeriod {
        struct ClassInsert: Encodable {
            let teacher_id: String
            let name: String
            let subject: String?
            let grade_level: String?
        }

        let insert = ClassInsert(
            teacher_id: teacherId.uuidString,
            name: name,
            subject: subject,
            grade_level: gradeLevel
        )

        let response: [ClassPeriod] = try await supabase.client
            .from("classes")
            .insert(insert)
            .select()
            .execute()
            .value

        if let created = response.first {
            classes.append(created)
            return created
        }
        throw NSError(domain: "SyncService", code: 1, userInfo: [NSLocalizedDescriptionKey: "Failed to create class"])
    }

    func deleteClass(classId: UUID) async throws {
        // Delete enrollments first, then the class
        try await supabase.client
            .from("class_students")
            .delete()
            .eq("class_id", value: classId.uuidString)
            .execute()

        try await supabase.client
            .from("classes")
            .delete()
            .eq("id", value: classId.uuidString)
            .execute()

        classes.removeAll { $0.id == classId }
    }

    func createStudent(firstName: String, lastName: String, studentIdNumber: String?, teacherId: UUID) async throws -> Student {
        struct StudentInsert: Encodable {
            let teacher_id: String
            let first_name: String
            let last_name: String
            let student_id_number: String?
            let is_active: Bool
        }

        let insert = StudentInsert(
            teacher_id: teacherId.uuidString,
            first_name: firstName,
            last_name: lastName,
            student_id_number: studentIdNumber,
            is_active: true
        )

        let response: [Student] = try await supabase.client
            .from("students")
            .insert(insert)
            .select()
            .execute()
            .value

        if let created = response.first {
            return created
        }
        throw NSError(domain: "SyncService", code: 2, userInfo: [NSLocalizedDescriptionKey: "Failed to create student"])
    }

    func addStudentToClass(studentId: UUID, classId: UUID) async throws {
        struct Enrollment: Encodable {
            let student_id: String
            let class_id: String
        }

        try await supabase.client
            .from("class_students")
            .insert(Enrollment(student_id: studentId.uuidString, class_id: classId.uuidString))
            .execute()
    }

    func removeStudentFromClass(studentId: UUID, classId: UUID) async throws {
        try await supabase.client
            .from("class_students")
            .delete()
            .eq("student_id", value: studentId.uuidString)
            .eq("class_id", value: classId.uuidString)
            .execute()
    }

    struct CSVStudent {
        let firstName: String
        let lastName: String
        let studentIdNumber: String?
    }

    static func parseCSV(_ content: String) -> [CSVStudent] {
        var results: [CSVStudent] = []
        let lines = content.components(separatedBy: .newlines)

        for (index, line) in lines.enumerated() {
            let trimmed = line.trimmingCharacters(in: .whitespacesAndNewlines)
            if trimmed.isEmpty { continue }
            // Skip header row
            if index == 0 && (trimmed.lowercased().contains("student") || trimmed.lowercased().contains("name")) {
                continue
            }

            let columns = trimmed.components(separatedBy: ",").map {
                $0.trimmingCharacters(in: .whitespacesAndNewlines)
                    .trimmingCharacters(in: CharacterSet(charactersIn: "\""))
            }
            guard !columns.isEmpty, !columns[0].isEmpty else { continue }

            let rawName = columns[0]
            let studentId = columns.count > 1 ? columns[1] : nil

            let firstName: String
            let lastName: String

            if rawName.contains(";") {
                // "Last; First Middle" format
                let parts = rawName.split(separator: ";", maxSplits: 1).map { $0.trimmingCharacters(in: .whitespaces) }
                lastName = parts[0]
                let firstParts = (parts.count > 1 ? parts[1] : "").split(separator: " ")
                firstName = firstParts.isEmpty ? "" : String(firstParts[0])
            } else {
                // "First Last" format
                let parts = rawName.split(separator: " ")
                firstName = parts.isEmpty ? "" : String(parts[0])
                lastName = parts.count > 1 ? parts.dropFirst().joined(separator: " ") : ""
            }

            results.append(CSVStudent(firstName: firstName, lastName: lastName, studentIdNumber: studentId))
        }
        return results
    }

    func importStudentsFromCSV(csvContent: String, classId: UUID, teacherId: UUID) async throws -> [Student] {
        let parsed = Self.parseCSV(csvContent)
        var imported: [Student] = []

        for entry in parsed {
            let student = try await createStudent(
                firstName: entry.firstName,
                lastName: entry.lastName,
                studentIdNumber: entry.studentIdNumber,
                teacherId: teacherId
            )
            try await addStudentToClass(studentId: student.id, classId: classId)
            imported.append(student)
        }

        return imported
    }

    // MARK: - Session Sync

    func syncSession(_ session: LocalSession, teacherId: UUID) async throws {
        guard isOnline else { return }

        struct SessionInsert: Encodable {
            let teacher_id: String
            let class_id: String?
            let period: String
            let date: String
            let started_at: String
            let ended_at: String?
            let device: String
            let is_active: Bool
        }

        let dateFormatter = ISO8601DateFormatter()
        let dateDayFormatter = DateFormatter()
        dateDayFormatter.dateFormat = "yyyy-MM-dd"

        let insert = SessionInsert(
            teacher_id: teacherId.uuidString,
            class_id: session.classId?.uuidString,
            period: session.period,
            date: dateDayFormatter.string(from: session.date),
            started_at: dateFormatter.string(from: session.startedAt),
            ended_at: session.endedAt.map { dateFormatter.string(from: $0) },
            device: "ios",
            is_active: session.isActive
        )

        struct SessionResponse: Decodable {
            let id: UUID
        }

        let response: [SessionResponse] = try await supabase.client
            .from("behavior_sessions")
            .insert(insert)
            .select("id")
            .execute()
            .value

        if let remoteId = response.first?.id {
            session.remoteId = remoteId
            session.syncStatus = .synced
        }
    }

    func syncEvent(_ event: LocalEvent, sessionRemoteId: UUID, teacherId: UUID) async throws {
        guard isOnline else { return }

        struct EventInsert: Encodable {
            let session_id: String
            let teacher_id: String
            let student_id: String?
            let student_name: String
            let type: String
            let note: String?
            let transcript: String?
            let source: String
            let event_time: String
            let client_id: String
        }

        let dateFormatter = ISO8601DateFormatter()

        let insert = EventInsert(
            session_id: sessionRemoteId.uuidString,
            teacher_id: teacherId.uuidString,
            student_id: event.studentId?.uuidString,
            student_name: event.studentName,
            type: event.typeRaw,
            note: event.note,
            transcript: event.transcript,
            source: event.sourceRaw,
            event_time: dateFormatter.string(from: event.eventTime),
            client_id: event.id.uuidString
        )

        struct EventResponse: Decodable {
            let id: UUID
        }

        do {
            let response: [EventResponse] = try await supabase.client
                .from("behavior_events")
                .insert(insert)
                .select("id")
                .execute()
                .value

            if let remoteId = response.first?.id {
                event.remoteId = remoteId
                event.syncStatus = .synced
            }
        } catch {
            // Check if duplicate client_id — means already synced
            let errorStr = String(describing: error)
            if errorStr.contains("duplicate") || errorStr.contains("unique") {
                event.syncStatus = .synced
            } else {
                event.syncStatus = .failed
                throw error
            }
        }
    }

    func deleteEvent(_ event: LocalEvent) async throws {
        // Delete from Supabase if synced
        if let remoteId = event.remoteId {
            try await supabase.client
                .from("behavior_events")
                .delete()
                .eq("id", value: remoteId.uuidString)
                .execute()
        }
    }

    func endSession(_ session: LocalSession, teacherId: UUID) async throws {
        guard let remoteId = session.remoteId, isOnline else { return }

        struct SessionUpdate: Encodable {
            let ended_at: String
            let is_active: Bool
        }

        let dateFormatter = ISO8601DateFormatter()
        let update = SessionUpdate(
            ended_at: dateFormatter.string(from: session.endedAt ?? .now),
            is_active: false
        )

        try await supabase.client
            .from("behavior_sessions")
            .update(update)
            .eq("id", value: remoteId.uuidString)
            .execute()
    }
}
