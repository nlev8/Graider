import Foundation
import Supabase

@MainActor
class AuthService: ObservableObject {
    @Published var isAuthenticated = false
    @Published var isLoading = true
    @Published var userId: UUID?
    @Published var userEmail: String?
    @Published var error: String?

    private let supabase: SupabaseManager

    init(supabase: SupabaseManager) {
        self.supabase = supabase
    }

    func restoreSession() async {
        isLoading = true
        defer { isLoading = false }

        do {
            let session = try await supabase.client.auth.session
            userId = session.user.id
            userEmail = session.user.email
            isAuthenticated = true
        } catch {
            isAuthenticated = false
            userId = nil
            userEmail = nil
        }
    }

    func signIn(email: String, password: String) async throws {
        error = nil
        do {
            let session = try await supabase.client.auth.signIn(
                email: email,
                password: password
            )
            userId = session.user.id
            userEmail = session.user.email
            isAuthenticated = true
        } catch {
            self.error = error.localizedDescription
            throw error
        }
    }

    func signOut() async {
        do {
            try await supabase.client.auth.signOut()
        } catch {
            // Sign out locally even if remote fails
        }
        isAuthenticated = false
        userId = nil
        userEmail = nil
    }
}
