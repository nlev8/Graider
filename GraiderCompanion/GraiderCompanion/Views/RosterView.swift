import SwiftUI

struct RosterView: View {
    @EnvironmentObject var authService: AuthService
    @EnvironmentObject var syncService: SyncService

    @State private var showAddClass = false
    @State private var showCSVImport = false
    @State private var error: String?
    @State private var isLoading = false
    var body: some View {
        List {
            if syncService.classes.isEmpty && !isLoading {
                ContentUnavailableView(
                    "No Classes",
                    systemImage: "person.3",
                    description: Text("Tap + to add a class or import from CSV.")
                )
            } else {
                ForEach(syncService.classes) { cls in
                    NavigationLink(destination: ClassDetailView(classPeriod: cls)) {
                        HStack {
                            VStack(alignment: .leading, spacing: 4) {
                                Text(cls.name)
                                    .font(.headline)
                                if let subject = cls.subject, !subject.isEmpty {
                                    Text(subject)
                                        .font(.subheadline)
                                        .foregroundStyle(.secondary)
                                }
                            }
                            Spacer()
                            Text("\(cls.studentCount)")
                                .font(.subheadline)
                                .foregroundStyle(.secondary)
                            Image(systemName: "person.2")
                                .font(.caption)
                                .foregroundStyle(.secondary)
                        }
                    }
                }
                .onDelete(perform: deleteClasses)
            }
        }
        .navigationTitle("Roster")
        .toolbar {
            ToolbarItemGroup(placement: .topBarTrailing) {
                Button {
                    showCSVImport = true
                } label: {
                    Image(systemName: "doc.text")
                }

                Button {
                    showAddClass = true
                } label: {
                    Image(systemName: "plus")
                }
            }
        }
        .overlay {
            if isLoading {
                ProgressView()
            }
        }
        .alert("Error", isPresented: .constant(error != nil)) {
            Button("OK") { error = nil }
        } message: {
            Text(error ?? "")
        }
        .sheet(isPresented: $showAddClass) {
            AddClassSheet()
        }
        .sheet(isPresented: $showCSVImport) {
            CSVImportView()
        }
        .task {
            await loadClasses()
        }
    }

    private func loadClasses() async {
        guard let userId = authService.userId else { return }
        isLoading = true
        do {
            try await syncService.fetchClasses(teacherId: userId)
        } catch {
            self.error = "Failed to load classes"
        }
        isLoading = false
    }

    private func deleteClasses(at offsets: IndexSet) {
        let classesToDelete = offsets.map { syncService.classes[$0] }
        for cls in classesToDelete {
            Task {
                do {
                    try await syncService.deleteClass(classId: cls.id)
                } catch {
                    self.error = "Failed to delete \(cls.name)"
                }
            }
        }
    }
}
