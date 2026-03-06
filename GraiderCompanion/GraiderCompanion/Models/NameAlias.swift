import Foundation
import SwiftData

@Model
class NameAlias {
    var id: UUID
    var studentId: UUID
    var variant: String
    var createdAt: Date

    init(studentId: UUID, variant: String) {
        self.id = UUID()
        self.studentId = studentId
        self.variant = variant
        self.createdAt = .now
    }
}
