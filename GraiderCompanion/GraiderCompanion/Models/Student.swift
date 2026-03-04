import Foundation

struct Student: Identifiable, Codable, Hashable {
    let id: UUID
    let firstName: String
    let lastName: String
    let email: String?
    let period: String?
    let studentIdNumber: String?

    var displayName: String {
        "\(firstName) \(lastName)"
    }

    var shortName: String {
        let lastInitial = lastName.prefix(1)
        return "\(firstName) \(lastInitial)."
    }

    enum CodingKeys: String, CodingKey {
        case id
        case firstName = "first_name"
        case lastName = "last_name"
        case email
        case period
        case studentIdNumber = "student_id_number"
    }
}
