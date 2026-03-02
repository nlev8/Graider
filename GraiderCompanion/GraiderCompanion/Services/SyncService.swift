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

    // MARK: - Fetch Classes & Students

    func fetchClasses(teacherId: UUID) async throws {
        let response: [ClassPeriod] = try await supabase.client
            .from("classes")
            .select()
            .eq("teacher_id", value: teacherId.uuidString)
            .execute()
            .value

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
