import SwiftUI

struct StudentTallyRow: View {
    let name: String
    let corrections: Int
    let praise: Int
    let onAddCorrection: () -> Void
    let onAddPraise: () -> Void

    var body: some View {
        HStack {
            Text(name)
                .font(.subheadline)
                .lineLimit(1)

            Spacer()

            // Corrections
            HStack(spacing: 4) {
                Button(action: onAddCorrection) {
                    Image(systemName: "minus.circle.fill")
                        .foregroundStyle(.red)
                }
                .buttonStyle(.plain)

                Text("\(corrections)")
                    .font(.subheadline.monospacedDigit())
                    .foregroundStyle(.red)
                    .frame(minWidth: 20)
            }

            // Praise
            HStack(spacing: 4) {
                Button(action: onAddPraise) {
                    Image(systemName: "plus.circle.fill")
                        .foregroundStyle(.green)
                }
                .buttonStyle(.plain)

                Text("\(praise)")
                    .font(.subheadline.monospacedDigit())
                    .foregroundStyle(.green)
                    .frame(minWidth: 20)
            }
        }
        .padding(.vertical, 6)
    }
}
