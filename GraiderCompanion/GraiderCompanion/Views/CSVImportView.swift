import SwiftUI
import UniformTypeIdentifiers

struct CSVImportView: View {
    @EnvironmentObject var authService: AuthService
    @EnvironmentObject var syncService: SyncService
    @Environment(\.dismiss) private var dismiss

    @State private var showFilePicker = false
    @State private var csvContent: String?
    @State private var fileName: String?
    @State private var parsedStudents: [SyncService.CSVStudent] = []
    @State private var selectedClassId: UUID?
    @State private var isImporting = false
    @State private var error: String?
    @State private var importedCount: Int?

    var body: some View {
        NavigationStack {
            Form {
                // Step 1: Pick CSV file
                Section("1. Select CSV File") {
                    Button {
                        showFilePicker = true
                    } label: {
                        HStack {
                            Image(systemName: "doc.text")
                            Text(fileName ?? "Choose CSV File...")
                                .foregroundStyle(fileName == nil ? .blue : .primary)
                        }
                    }

                    if !parsedStudents.isEmpty {
                        Text("\(parsedStudents.count) students found")
                            .font(.caption)
                            .foregroundStyle(.green)
                    }
                }

                // Step 2: Preview parsed students
                if !parsedStudents.isEmpty {
                    Section("2. Preview (\(parsedStudents.count) students)") {
                        ForEach(Array(parsedStudents.prefix(10).enumerated()), id: \.offset) { _, student in
                            HStack {
                                Text("\(student.firstName) \(student.lastName)")
                                Spacer()
                                if let sid = student.studentIdNumber, !sid.isEmpty {
                                    Text(sid)
                                        .font(.caption)
                                        .foregroundStyle(.secondary)
                                }
                            }
                        }
                        if parsedStudents.count > 10 {
                            Text("... and \(parsedStudents.count - 10) more")
                                .font(.caption)
                                .foregroundStyle(.secondary)
                        }
                    }

                    // Step 3: Select target class
                    Section("3. Import Into Class") {
                        if syncService.classes.isEmpty {
                            Text("No classes available. Create a class first.")
                                .font(.caption)
                                .foregroundStyle(.secondary)
                        } else {
                            Picker("Class", selection: $selectedClassId) {
                                Text("Select a class...").tag(UUID?.none)
                                ForEach(syncService.classes) { cls in
                                    Text(cls.name).tag(UUID?.some(cls.id))
                                }
                            }
                        }
                    }
                }

                if let error {
                    Section {
                        Text(error)
                            .foregroundStyle(.red)
                            .font(.caption)
                    }
                }

                if let count = importedCount {
                    Section {
                        Label("\(count) students imported successfully!", systemImage: "checkmark.circle.fill")
                            .foregroundStyle(.green)
                    }
                }
            }
            .navigationTitle("Import CSV")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    if importedCount != nil {
                        Button("Done") { dismiss() }
                    } else {
                        Button("Import") {
                            Task { await doImport() }
                        }
                        .disabled(parsedStudents.isEmpty || selectedClassId == nil || isImporting)
                    }
                }
            }
            .overlay {
                if isImporting {
                    VStack(spacing: 12) {
                        ProgressView()
                        Text("Importing students...")
                            .font(.caption)
                    }
                    .padding()
                    .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 12))
                }
            }
            .fileImporter(isPresented: $showFilePicker, allowedContentTypes: [UTType.commaSeparatedText, UTType.plainText]) { result in
                handleFile(result)
            }
        }
    }

    private func handleFile(_ result: Result<URL, Error>) {
        switch result {
        case .success(let url):
            guard url.startAccessingSecurityScopedResource() else {
                error = "Cannot access file"
                return
            }
            defer { url.stopAccessingSecurityScopedResource() }

            do {
                let content = try String(contentsOf: url, encoding: .utf8)
                csvContent = content
                fileName = url.lastPathComponent
                parsedStudents = SyncService.parseCSV(content)
                error = nil
                if parsedStudents.isEmpty {
                    error = "No students found in CSV. Expected format: Last; First,StudentID,..."
                }
            } catch {
                self.error = "Failed to read file: \(error.localizedDescription)"
            }
        case .failure(let err):
            error = "File picker error: \(err.localizedDescription)"
        }
    }

    private func doImport() async {
        guard let userId = authService.userId,
              let classId = selectedClassId,
              let content = csvContent else { return }

        isImporting = true
        error = nil

        do {
            let imported = try await syncService.importStudentsFromCSV(
                csvContent: content,
                classId: classId,
                teacherId: userId
            )
            importedCount = imported.count
            // Refresh class list to update student counts
            try? await syncService.fetchClasses(teacherId: userId)
        } catch {
            self.error = "Import failed: \(error.localizedDescription)"
        }

        isImporting = false
    }
}
