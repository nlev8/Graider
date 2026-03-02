import Foundation

struct ClassPeriod: Identifiable, Codable, Hashable {
    let id: UUID
    let name: String
    let subject: String?
    let gradeLevel: String?
    let joinCode: String?

    var studentCount: Int = 0

    enum CodingKeys: String, CodingKey {
        case id
        case name
        case subject
        case gradeLevel = "grade_level"
        case joinCode = "join_code"
    }
}
