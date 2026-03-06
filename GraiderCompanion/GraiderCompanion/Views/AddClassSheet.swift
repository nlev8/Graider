import SwiftUI

struct AddClassSheet: View {
    @EnvironmentObject var authService: AuthService
    @EnvironmentObject var syncService: SyncService
    @Environment(\.dismiss) private var dismiss

    @State private var name = ""
    @State private var subject = ""
    @State private var gradeLevel = ""
    @State private var isSaving = false
    @State private var error: String?

    var body: some View {
        NavigationStack {
            Form {
                Section("Class Info") {
                    TextField("Class Name (e.g. Period 1)", text: $name)
                    TextField("Subject (optional)", text: $subject)
                    TextField("Grade Level (optional)", text: $gradeLevel)
                        .keyboardType(.numberPad)
                }

                if let error {
                    Section {
                        Text(error)
                            .foregroundStyle(.red)
                            .font(.caption)
                    }
                }
            }
            .navigationTitle("Add Class")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Save") {
                        Task { await save() }
                    }
                    .disabled(name.trimmingCharacters(in: .whitespaces).isEmpty || isSaving)
                }
            }
            .overlay {
                if isSaving {
                    ProgressView()
                }
            }
        }
    }

    private func save() async {
        guard let userId = authService.userId else { return }
        isSaving = true
        error = nil

        do {
            _ = try await syncService.createClass(
                name: name.trimmingCharacters(in: .whitespaces),
                subject: subject.isEmpty ? nil : subject,
                gradeLevel: gradeLevel.isEmpty ? nil : gradeLevel,
                teacherId: userId
            )
            dismiss()
        } catch {
            self.error = "Failed to create class: \(error.localizedDescription)"
        }

        isSaving = false
    }
}
