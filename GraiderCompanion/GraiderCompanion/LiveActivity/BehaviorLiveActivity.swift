import SwiftUI
import WidgetKit
import ActivityKit

struct BehaviorLiveActivity: Widget {
    var body: some WidgetConfiguration {
        ActivityConfiguration(for: BehaviorActivityAttributes.self) { context in
            // Lock Screen / StandBy view
            HStack {
                VStack(alignment: .leading, spacing: 4) {
                    Text(context.attributes.period)
                        .font(.headline)
                    Text("\(context.state.elapsedMinutes)m elapsed")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }

                Spacer()

                HStack(spacing: 16) {
                    VStack {
                        Text("\(context.state.totalCorrections)")
                            .font(.title2.bold())
                            .foregroundStyle(.red)
                        Text("-")
                            .font(.caption2)
                            .foregroundStyle(.secondary)
                    }
                    VStack {
                        Text("\(context.state.totalPraise)")
                            .font(.title2.bold())
                            .foregroundStyle(.green)
                        Text("+")
                            .font(.caption2)
                            .foregroundStyle(.secondary)
                    }
                }
            }
            .padding()
        } dynamicIsland: { context in
            DynamicIsland {
                // Expanded
                DynamicIslandExpandedRegion(.leading) {
                    VStack(alignment: .leading) {
                        Text(context.attributes.period)
                            .font(.headline)
                        Text("\(context.state.elapsedMinutes)m")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                }
                DynamicIslandExpandedRegion(.trailing) {
                    HStack(spacing: 12) {
                        Label("\(context.state.totalCorrections)", systemImage: "minus.circle.fill")
                            .foregroundStyle(.red)
                        Label("\(context.state.totalPraise)", systemImage: "plus.circle.fill")
                            .foregroundStyle(.green)
                    }
                    .font(.subheadline)
                }
                DynamicIslandExpandedRegion(.bottom) {
                    if let name = context.state.lastStudentName {
                        Text("Last: \(name)")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                }
            } compactLeading: {
                Text(String(context.attributes.period.prefix(2)))
                    .font(.caption2.bold())
            } compactTrailing: {
                HStack(spacing: 4) {
                    Text("-\(context.state.totalCorrections)")
                        .foregroundStyle(.red)
                    Text("+\(context.state.totalPraise)")
                        .foregroundStyle(.green)
                }
                .font(.caption2.monospacedDigit())
            } minimal: {
                Image(systemName: "graduationcap.fill")
                    .foregroundStyle(.blue)
            }
        }
    }
}
