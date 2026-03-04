import Foundation
import SwiftData

enum SyncStatus: String, Codable {
    case pending
    case syncing
    case synced
    case failed
}

enum EventType: String, Codable {
    case correction
    case praise
}

enum EventSource: String, Codable {
    case manual
    case stt
    case watch
}

@Model
class LocalEvent {
    var id: UUID
    var remoteId: UUID?
    var studentId: UUID?
    var studentName: String
    var typeRaw: String
    var note: String?
    var transcript: String?
    var sourceRaw: String
    var eventTime: Date
    var syncStatusRaw: String

    var session: LocalSession?

    var type: EventType {
        get { EventType(rawValue: typeRaw) ?? .correction }
        set { typeRaw = newValue.rawValue }
    }

    var source: EventSource {
        get { EventSource(rawValue: sourceRaw) ?? .manual }
        set { sourceRaw = newValue.rawValue }
    }

    var syncStatus: SyncStatus {
        get { SyncStatus(rawValue: syncStatusRaw) ?? .pending }
        set { syncStatusRaw = newValue.rawValue }
    }

    init(
        studentId: UUID? = nil,
        studentName: String,
        type: EventType,
        source: EventSource = .manual,
        note: String? = nil,
        transcript: String? = nil
    ) {
        self.id = UUID()
        self.remoteId = nil
        self.studentId = studentId
        self.studentName = studentName
        self.typeRaw = type.rawValue
        self.note = note
        self.transcript = transcript
        self.sourceRaw = source.rawValue
        self.eventTime = .now
        self.syncStatusRaw = SyncStatus.pending.rawValue
    }
}
