import Foundation
import SwiftData

@Model
class LocalSession {
    var id: UUID
    var remoteId: UUID?
    var classId: UUID?
    var period: String
    var date: Date
    var startedAt: Date
    var endedAt: Date?
    var isActive: Bool
    var syncStatusRaw: String
    var lastSyncAttempt: Date?
    var syncError: String?

    @Relationship(deleteRule: .cascade, inverse: \LocalEvent.session)
    var events: [LocalEvent]

    var syncStatus: SyncStatus {
        get { SyncStatus(rawValue: syncStatusRaw) ?? .pending }
        set { syncStatusRaw = newValue.rawValue }
    }

    init(
        classId: UUID? = nil,
        period: String,
        date: Date = .now
    ) {
        self.id = UUID()
        self.remoteId = nil
        self.classId = classId
        self.period = period
        self.date = date
        self.startedAt = .now
        self.endedAt = nil
        self.isActive = true
        self.syncStatusRaw = SyncStatus.pending.rawValue
        self.lastSyncAttempt = nil
        self.syncError = nil
        self.events = []
    }
}
