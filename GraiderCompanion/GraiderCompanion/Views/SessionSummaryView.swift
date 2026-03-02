import SwiftUI

struct SessionSummaryView: View {
    let events: [LocalEvent]
    @Environment(\.dismiss) private var dismiss

    private var totalCorrections: Int {
        events.filter { $0.type == .correction }.count
    }

    private var totalPraise: Int {
        events.filter { $0.type == .praise }.count
    }

    private struct StudentSummary: Identifiable {
        let id = UUID()
        let name: String
        let corrections: Int
        let praise: Int
    }

    private var studentSummaries: [StudentSummary] {
        var dict: [String: (corrections: Int, praise: Int)] = [:]
        for event in events {
            var entry = dict[event.studentName] ?? (0, 0)
            if event.type == .correction {
                entry.corrections += 1
            } else {
                entry.praise += 1
            }
            dict[event.studentName] = entry
        }
        return dict.map { StudentSummary(name: $0.key, corrections: $0.value.corrections, praise: $0.value.praise) }
            .sorted { $0.corrections > $1.corrections }
    }

    var body: some View {
        NavigationStack {
            VStack(spacing: 24) {
                // Summary stats
                HStack(spacing: 32) {
                    VStack {
                        Text("\(totalCorrections)")
                            .font(.largeTitle.bold())
                            .foregroundStyle(.red)
                        Text("Corrections")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }

                    VStack {
                        Text("\(totalPraise)")
                            .font(.largeTitle.bold())
                            .foregroundStyle(.green)
                        Text("Praise")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }

                    VStack {
                        Text("\(events.count)")
                            .font(.largeTitle.bold())
                        Text("Total")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                }
                .padding()

                // Per-student breakdown
                if !studentSummaries.isEmpty {
                    List(studentSummaries) { summary in
                        HStack {
                            Text(summary.name)
                            Spacer()
                            if summary.corrections > 0 {
                                Text("-\(summary.corrections)")
                                    .foregroundStyle(.red)
                                    .monospacedDigit()
                            }
                            if summary.praise > 0 {
                                Text("+\(summary.praise)")
                                    .foregroundStyle(.green)
                                    .monospacedDigit()
                            }
                        }
                    }
                    .listStyle(.plain)
                }

                // Sync status
                HStack {
                    let syncedCount = events.filter { $0.syncStatus == .synced }.count
                    if syncedCount == events.count {
                        Label("Session saved and synced", systemImage: "checkmark.circle.fill")
                            .foregroundStyle(.green)
                    } else {
                        Label("Saved locally, will sync when online", systemImage: "icloud.and.arrow.up")
                            .foregroundStyle(.orange)
                    }
                }
                .font(.caption)
                .padding()
            }
            .navigationTitle("Session Summary")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    Button("Done") { dismiss() }
                }
            }
        }
    }
}
