import SwiftUI
import SwiftData

struct HomeView: View {
    @EnvironmentObject var authService: AuthService
    @EnvironmentObject var syncService: SyncService
    @Environment(\.modelContext) private var modelContext

    @State private var selectedClass: ClassPeriod?
    @State private var students: [Student] = []
    @State private var isLoadingStudents = false
    @State private var showSession = false
    @State private var error: String?

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                // Greeting
                VStack(alignment: .leading, spacing: 4) {
                    Text(greeting)
                        .font(.title2.bold())
                    if !syncService.isOnline {
                        Label("Offline", systemImage: "wifi.slash")
                            .font(.caption)
                            .foregroundStyle(.orange)
                    }
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding()

                if syncService.classes.isEmpty {
                    ContentUnavailableView(
                        "No Classes",
                        systemImage: "person.3",
                        description: Text("Add classes in the Graider web app to get started.")
                    )
                } else {
                    // Class list
                    ScrollView {
                        VStack(spacing: 12) {
                            Text("Select a class:")
                                .font(.headline)
                                .frame(maxWidth: .infinity, alignment: .leading)

                            ForEach(syncService.classes) { cls in
                                ClassCard(
                                    classPeriod: cls,
                                    isSelected: selectedClass?.id == cls.id,
                                    studentCount: selectedClass?.id == cls.id ? students.count : cls.studentCount
                                )
                                .onTapGesture {
                                    selectClass(cls)
                                }
                            }
                        }
                        .padding()
                    }

                    if let error {
                        Text(error)
                            .font(.caption)
                            .foregroundStyle(.red)
                            .padding(.horizontal)
                    }

                    // Start Session button
                    Button {
                        showSession = true
                    } label: {
                        HStack {
                            Image(systemName: "play.fill")
                            Text("Start Session")
                                .fontWeight(.semibold)
                        }
                        .frame(maxWidth: .infinity)
                        .frame(height: 50)
                    }
                    .buttonStyle(.borderedProminent)
                    .tint(.green)
                    .disabled(selectedClass == nil || isLoadingStudents)
                    .padding()
                }
            }
            .navigationTitle("Graider")
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button {
                        Task { await authService.signOut() }
                    } label: {
                        Image(systemName: "rectangle.portrait.and.arrow.right")
                    }
                }
            }
            .task {
                await loadClasses()
            }
            .fullScreenCover(isPresented: $showSession) {
                if let selectedClass {
                    SessionView(
                        classPeriod: selectedClass,
                        students: students
                    )
                }
            }
        }
    }

    private var greeting: String {
        let hour = Calendar.current.component(.hour, from: .now)
        let name = authService.userEmail?.components(separatedBy: "@").first ?? ""
        let capitalizedName = name.prefix(1).uppercased() + name.dropFirst()
        if hour < 12 {
            return "Good morning, \(capitalizedName)!"
        } else if hour < 17 {
            return "Good afternoon, \(capitalizedName)!"
        } else {
            return "Good evening, \(capitalizedName)!"
        }
    }

    private func loadClasses() async {
        guard let userId = authService.userId else { return }
        do {
            try await syncService.fetchClasses(teacherId: userId)
        } catch {
            self.error = "Failed to load classes"
        }
    }

    private func selectClass(_ cls: ClassPeriod) {
        selectedClass = cls
        isLoadingStudents = true
        error = nil

        Task {
            do {
                students = try await syncService.fetchStudents(classId: cls.id)
                isLoadingStudents = false
            } catch {
                self.error = "Failed to load students"
                isLoadingStudents = false
            }
        }
    }
}

struct ClassCard: View {
    let classPeriod: ClassPeriod
    let isSelected: Bool
    let studentCount: Int

    var body: some View {
        HStack {
            VStack(alignment: .leading, spacing: 4) {
                Text(classPeriod.name)
                    .font(.headline)
                if let subject = classPeriod.subject, !subject.isEmpty {
                    Text(subject)
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                }
                Text("\(studentCount) students")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }

            Spacer()

            if isSelected {
                Image(systemName: "checkmark.circle.fill")
                    .foregroundStyle(.blue)
                    .font(.title3)
            }
        }
        .padding()
        .background(
            RoundedRectangle(cornerRadius: 12)
                .fill(isSelected ? Color.blue.opacity(0.1) : Color(.systemGray6))
        )
        .overlay(
            RoundedRectangle(cornerRadius: 12)
                .stroke(isSelected ? Color.blue : Color.clear, lineWidth: 2)
        )
    }
}
