import SwiftUI

struct LoginView: View {
    @EnvironmentObject var authService: AuthService
    @State private var email = ""
    @State private var password = ""
    @State private var isLoading = false
    @State private var showPassword = false

    var body: some View {
        VStack(spacing: 0) {
            Spacer()

            // Logo area
            VStack(spacing: 12) {
                Image(systemName: "graduationcap.fill")
                    .font(.system(size: 60))
                    .foregroundStyle(.blue)

                Text("Graider")
                    .font(.largeTitle.bold())

                Text("Classroom Companion")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
            }
            .padding(.bottom, 48)

            // Login form
            VStack(spacing: 16) {
                TextField("Email", text: $email)
                    .textFieldStyle(.roundedBorder)
                    .textContentType(.emailAddress)
                    .keyboardType(.emailAddress)
                    .autocapitalization(.none)
                    .autocorrectionDisabled()

                HStack {
                    Group {
                        if showPassword {
                            TextField("Password", text: $password)
                        } else {
                            SecureField("Password", text: $password)
                        }
                    }
                    .textFieldStyle(.roundedBorder)
                    .textContentType(.password)

                    Button {
                        showPassword.toggle()
                    } label: {
                        Image(systemName: showPassword ? "eye.slash" : "eye")
                            .foregroundStyle(.secondary)
                    }
                }

                if let error = authService.error {
                    Text(error)
                        .font(.caption)
                        .foregroundStyle(.red)
                        .multilineTextAlignment(.center)
                }

                Button {
                    Task { await signIn() }
                } label: {
                    Group {
                        if isLoading {
                            ProgressView()
                                .tint(.white)
                        } else {
                            Text("Sign In")
                                .fontWeight(.semibold)
                        }
                    }
                    .frame(maxWidth: .infinity)
                    .frame(height: 44)
                }
                .buttonStyle(.borderedProminent)
                .disabled(email.isEmpty || password.isEmpty || isLoading)
            }
            .padding(.horizontal, 32)

            Spacer()

            Text("Sign in with your Graider account")
                .font(.caption)
                .foregroundStyle(.secondary)
                .padding(.bottom, 24)
        }
    }

    private func signIn() async {
        isLoading = true
        defer { isLoading = false }

        do {
            try await authService.signIn(email: email, password: password)
        } catch {
            // Error is set by authService
        }
    }
}
