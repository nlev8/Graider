import Foundation
import Supabase

final class SupabaseManager {
    static let shared = SupabaseManager()

    let client: SupabaseClient

    private init() {
        let url = URL(string: "https://hecxqiedfodnpujjriin.supabase.co")!
        let anonKey = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImhlY3hxaWVkZm9kbnB1ampyaWluIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Njk4OTA3ODMsImV4cCI6MjA4NTQ2Njc4M30.KUvoxjmnCbZSUZo2a8nIj0UD56KM-CXB0dpZ1iYMwLE"

        self.client = SupabaseClient(
            supabaseURL: url,
            supabaseKey: anonKey
        )
    }
}
