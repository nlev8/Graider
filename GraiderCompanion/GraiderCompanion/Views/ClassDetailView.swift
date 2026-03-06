import SwiftUI

struct ClassDetailView: View {
    let classPeriod: ClassPeriod

    @EnvironmentObject var authService: AuthService
    @EnvironmentObject var syncService: SyncService

    @State private var students: [Student] = []
    @State private var isLoading = false
    @State private var error: String?
    @State private var showAddStudent = false
    @State private var newFirstName = ""
    @State private var newLastName = ""

    var body: some View {
        List {
            if students.isEmpty && !isLoading {
                ContentUnavailableView(
                    "No Students",
                    systemImage: "person",
                    description: Text("Add students manually or import from CSV.")
                )
            } else {
                ForEach(students) { student in
                    HStack {
                        VStack(alignment: .leading, spacing: 2) {
                            Text(student.displayName)
                                .font(.body)
                            if let sid = student.studentIdNumber, !sid.isEmpty {
                                Text("ID: \(sid)")
                                    .font(.caption)
                                    .foregroundStyle(.secondary)
                            }
                        }
                    }
                }
                .onDelete(perform: removeStudents)
            }
        }
        .navigationTitle(classPeriod.name)
        .toolbar {
            ToolbarItem(placement: .topBarTrailing) {
                Button {
                    showAddStudent = true
                } label: {
                    Image(systemName: "person.badge.plus")
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
        .alert("Add Student", isPresented: $showAddStudent) {
            TextField("First Name", text: $newFirstName)
            TextField("Last Name", text: $newLastName)
            Button("Cancel", role: .cancel) {
                newFirstName = ""
                newLastName = ""
            }
            Button("Add") {
                Task { await addStudent() }
            }
        }
        .task {
            await loadStudents()
        }
    }

    private func loadStudents() async {
        isLoading = true
        do {
            students = try await syncService.fetchStudents(classId: classPeriod.id)
        } catch {
            self.error = "Failed to load students"
        }
        isLoading = false
    }

    private func addStudent() async {
        guard let userId = authService.userId else { return }
        let first = newFirstName.trimmingCharacters(in: .whitespaces)
        let last = newLastName.trimmingCharacters(in: .whitespaces)
        guard !first.isEmpty, !last.isEmpty else { return }

        do {
            let student = try await syncService.createStudent(
                firstName: first,
                lastName: last,
                studentIdNumber: nil,
                teacherId: userId
            )
            try await syncService.addStudentToClass(studentId: student.id, classId: classPeriod.id)
            students.append(student)
            students.sort { $0.lastName < $1.lastName }
        } catch {
            self.error = "Failed to add student"
        }

        newFirstName = ""
        newLastName = ""
    }

    private func removeStudents(at offsets: IndexSet) {
        let toRemove = offsets.map { students[$0] }
        for student in toRemove {
            Task {
                do {
                    try await syncService.removeStudentFromClass(studentId: student.id, classId: classPeriod.id)
                } catch {
                    self.error = "Failed to remove \(student.displayName)"
                }
            }
        }
        students.remove(atOffsets: offsets)
    }
}
