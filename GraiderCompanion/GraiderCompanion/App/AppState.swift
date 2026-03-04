import SwiftUI

@MainActor
class AppState: ObservableObject {
    let authService: AuthService
    let syncService: SyncService

    init() {
        let supabase = SupabaseManager.shared
        self.authService = AuthService(supabase: supabase)
        self.syncService = SyncService(supabase: supabase)
    }
}
