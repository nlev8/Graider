import SwiftUI
import SwiftData

@main
struct GraiderCompanionApp: App {
    @StateObject private var appState = AppState()

    var sharedModelContainer: ModelContainer = {
        let schema = Schema([
            LocalSession.self,
            LocalEvent.self,
        ])
        let config = ModelConfiguration(schema: schema, isStoredInMemoryOnly: false)
        do {
            return try ModelContainer(for: schema, configurations: [config])
        } catch {
            fatalError("Could not create ModelContainer: \(error)")
        }
    }()

    var body: some Scene {
        WindowGroup {
            RootView()
                .environmentObject(appState)
                .environmentObject(appState.authService)
                .environmentObject(appState.syncService)
        }
        .modelContainer(sharedModelContainer)
    }
}

struct RootView: View {
    @EnvironmentObject var authService: AuthService

    var body: some View {
        Group {
            if authService.isLoading {
                ProgressView("Loading...")
            } else if authService.isAuthenticated {
                HomeView()
            } else {
                LoginView()
            }
        }
        .task {
            await authService.restoreSession()
        }
    }
}
