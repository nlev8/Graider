import ActivityKit
import SwiftUI

struct BehaviorActivityAttributes: ActivityAttributes {
    struct ContentState: Codable, Hashable {
        var totalCorrections: Int
        var totalPraise: Int
        var lastStudentName: String?
        var lastEventType: String?
        var elapsedMinutes: Int
    }

    var period: String
    var startTime: Date
}
