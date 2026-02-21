/* ============================================
   GRAIDER LANDING PAGE - JAVASCRIPT
   ============================================ */

// Supabase client
const supabaseClient = window.supabase.createClient(
    'https://hecxqiedfodnpujjriin.supabase.co',
    'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImhlY3hxaWVkZm9kbnB1ampyaWluIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Njk4OTA3ODMsImV4cCI6MjA4NTQ2Njc4M30.KUvoxjmnCbZSUZo2a8nIj0UD56KM-CXB0dpZ1iYMwLE'
);

// DOM Elements
const navbar = document.getElementById('navbar');
const mobileMenuBtn = document.getElementById('mobile-menu-btn');
const mobileMenu = document.getElementById('mobile-menu');
const loginModal = document.getElementById('login-modal');
const loginForm = document.getElementById('login-form');
const signupForm = document.getElementById('signup-form');
const forgotForm = document.getElementById('forgot-form');

// ============================================
// NAVIGATION
// ============================================

// Navbar scroll effect
let lastScrollY = 0;

function handleScroll() {
    const currentScrollY = window.scrollY;

    if (currentScrollY > 50) {
        navbar.classList.add('scrolled');
    } else {
        navbar.classList.remove('scrolled');
    }

    lastScrollY = currentScrollY;
}

window.addEventListener('scroll', handleScroll, { passive: true });

// Mobile menu toggle
function toggleMobileMenu() {
    mobileMenuBtn.classList.toggle('active');
    mobileMenu.classList.toggle('active');
    document.body.style.overflow = mobileMenu.classList.contains('active') ? 'hidden' : '';
}

function closeMobileMenu() {
    mobileMenuBtn.classList.remove('active');
    mobileMenu.classList.remove('active');
    document.body.style.overflow = '';
}

mobileMenuBtn.addEventListener('click', toggleMobileMenu);

// Close mobile menu on window resize
window.addEventListener('resize', function() {
    if (window.innerWidth > 768 && mobileMenu.classList.contains('active')) {
        closeMobileMenu();
    }
});

// ============================================
// MODAL FUNCTIONS
// ============================================

function openLoginModal(mode) {
    loginModal.classList.add('active');
    document.body.style.overflow = 'hidden';

    // Reset forms
    loginForm.style.display = 'none';
    signupForm.style.display = 'none';
    forgotForm.style.display = 'none';

    // Show appropriate form
    if (mode === 'signup') {
        signupForm.style.display = 'block';
    } else {
        loginForm.style.display = 'block';
    }
}

function closeLoginModal() {
    loginModal.classList.remove('active');
    document.body.style.overflow = '';
}

function showLoginForm(event) {
    if (event) event.preventDefault();
    loginForm.style.display = 'block';
    signupForm.style.display = 'none';
    forgotForm.style.display = 'none';
}

function showSignupForm(event) {
    if (event) event.preventDefault();
    loginForm.style.display = 'none';
    signupForm.style.display = 'block';
    forgotForm.style.display = 'none';
}

function showForgotPassword(event) {
    if (event) event.preventDefault();
    loginForm.style.display = 'none';
    signupForm.style.display = 'none';
    forgotForm.style.display = 'block';
}

// Close modal on overlay click
loginModal.addEventListener('click', function(event) {
    if (event.target === loginModal) {
        closeLoginModal();
    }
});

// Close modal on Escape key
document.addEventListener('keydown', function(event) {
    if (event.key === 'Escape' && loginModal.classList.contains('active')) {
        closeLoginModal();
    }
});

// ============================================
// FORM HANDLERS
// ============================================

function handleLogin(event) {
    event.preventDefault();
    var email = document.getElementById('login-email').value;
    var password = document.getElementById('login-password').value;

    if (!email || !password) {
        showFormError('Please fill in all fields');
        return;
    }

    var submitBtn = event.target.querySelector('button[type="submit"]');
    var originalText = submitBtn.textContent;
    submitBtn.textContent = 'Signing in...';
    submitBtn.disabled = true;

    supabaseClient.auth.signInWithPassword({ email: email, password: password })
        .then(function(result) {
            if (result.error) {
                if (result.error.message.indexOf('Email not confirmed') >= 0) {
                    showFormError('Please confirm your email first. Check your inbox.');
                } else {
                    showFormError(result.error.message);
                }
                submitBtn.textContent = originalText;
                submitBtn.disabled = false;
                return;
            }
            window.location.href = 'https://app.graider.live';
        })
        .catch(function(err) {
            showFormError('Something went wrong. Please try again.');
            submitBtn.textContent = originalText;
            submitBtn.disabled = false;
        });
}

function handleGoogleAuth() {
    supabaseClient.auth.signInWithOAuth({
        provider: 'google',
        options: { redirectTo: 'https://app.graider.live' }
    }).then(function(result) {
        if (result.error) {
            showFormError(result.error.message);
        }
    }).catch(function() {
        showFormError('Google sign-in failed. Please try again.');
    });
}

function handleMicrosoftAuth() {
    supabaseClient.auth.signInWithOAuth({
        provider: 'azure',
        options: {
            redirectTo: 'https://app.graider.live',
            scopes: 'email profile openid',
        }
    }).then(function(result) {
        if (result.error) {
            showFormError(result.error.message);
        }
    }).catch(function() {
        showFormError('Microsoft sign-in failed. Please try again.');
    });
}

function handleSignup(event) {
    event.preventDefault();
    var firstName = document.getElementById('signup-first').value;
    var lastName = document.getElementById('signup-last').value;
    var email = document.getElementById('signup-email').value;
    var password = document.getElementById('signup-password').value;
    var terms = document.getElementById('terms').checked;

    if (!firstName || !lastName || !email || !password) {
        showFormError('Please fill in all fields');
        return;
    }

    if (password.length < 6) {
        showFormError('Password must be at least 6 characters');
        return;
    }

    if (!terms) {
        showFormError('Please accept the terms and conditions');
        return;
    }

    var submitBtn = event.target.querySelector('button[type="submit"]');
    submitBtn.textContent = 'Creating account...';
    submitBtn.disabled = true;

    supabaseClient.auth.signUp({
        email: email,
        password: password,
        options: {
            data: {
                first_name: firstName,
                last_name: lastName,
            },
            emailRedirectTo: 'https://app.graider.live',
        }
    })
    .then(function(result) {
        if (result.error) {
            showFormError(result.error.message);
            submitBtn.textContent = 'Create Account';
            submitBtn.disabled = false;
            return;
        }

        // Notify admin of new signup (fire-and-forget)
        fetch('https://app.graider.live/api/auth/notify-signup', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email: email, first_name: firstName, last_name: lastName }),
        }).catch(function() {});

        // Show confirmation message
        var formContent = event.target.parentElement;
        formContent.innerHTML = '<div style="text-align:center;padding:20px 0;">' +
            '<div style="font-size:3rem;margin-bottom:16px;">&#9993;</div>' +
            '<h2 style="margin-bottom:12px;">Check your email</h2>' +
            '<p style="color:rgba(255,255,255,0.6);margin-bottom:24px;">' +
            'We sent a confirmation link to <strong>' + email + '</strong>. ' +
            'Click the link to activate your account, then sign in at the app.</p>' +
            '<a href="https://app.graider.live" class="btn btn-primary" style="display:inline-flex;">Go to App</a>' +
            '</div>';
    })
    .catch(function(err) {
        showFormError('Something went wrong. Please try again.');
        submitBtn.textContent = 'Create Account';
        submitBtn.disabled = false;
    });
}

function handleForgotPassword(event) {
    event.preventDefault();
    var email = document.getElementById('forgot-email').value;

    if (!email) {
        showFormError('Please enter your email');
        return;
    }

    var submitBtn = event.target.querySelector('button[type="submit"]');
    submitBtn.textContent = 'Sending...';
    submitBtn.disabled = true;

    supabaseClient.auth.resetPasswordForEmail(email, {
        redirectTo: 'https://app.graider.live',
    })
    .then(function(result) {
        if (result.error) {
            showFormError(result.error.message);
            submitBtn.textContent = 'Send Reset Link';
            submitBtn.disabled = false;
            return;
        }

        submitBtn.textContent = 'Link Sent!';
        submitBtn.style.background = '#22c55e';

        setTimeout(function() {
            showLoginForm();
            submitBtn.textContent = 'Send Reset Link';
            submitBtn.style.background = '';
            submitBtn.disabled = false;
        }, 2000);
    })
    .catch(function(err) {
        showFormError('Something went wrong. Please try again.');
        submitBtn.textContent = 'Send Reset Link';
        submitBtn.disabled = false;
    });
}

function showFormError(message) {
    // Simple alert for now - can be enhanced with toast notifications
    alert(message);
}

// ============================================
// PASSWORD TOGGLE
// ============================================

function togglePassword(inputId) {
    const input = document.getElementById(inputId);
    const btn = input.parentElement.querySelector('.password-toggle');
    const eyeOpen = btn.querySelector('.eye-open');
    const eyeClosed = btn.querySelector('.eye-closed');

    if (input.type === 'password') {
        input.type = 'text';
        eyeOpen.style.display = 'none';
        eyeClosed.style.display = 'block';
    } else {
        input.type = 'password';
        eyeOpen.style.display = 'block';
        eyeClosed.style.display = 'none';
    }
}

// ============================================
// SCROLL ANIMATIONS (Intersection Observer)
// ============================================

function initScrollAnimations() {
    const observerOptions = {
        root: null,
        rootMargin: '0px 0px -100px 0px',
        threshold: 0.1
    };

    const observer = new IntersectionObserver(function(entries) {
        entries.forEach(function(entry) {
            if (entry.isIntersecting) {
                entry.target.classList.add('animate');
                observer.unobserve(entry.target);
            }
        });
    }, observerOptions);

    // Observe all elements with data-animate attribute
    const animatedElements = document.querySelectorAll('[data-animate]');
    animatedElements.forEach(function(element) {
        observer.observe(element);
    });
}

// ============================================
// SMOOTH SCROLL FOR ANCHOR LINKS
// ============================================

function initSmoothScroll() {
    const anchorLinks = document.querySelectorAll('a[href^="#"]');

    anchorLinks.forEach(function(link) {
        link.addEventListener('click', function(event) {
            const href = this.getAttribute('href');

            if (href === '#') return;

            const target = document.querySelector(href);

            if (target) {
                event.preventDefault();

                const navbarHeight = navbar.offsetHeight;
                const targetPosition = target.getBoundingClientRect().top + window.pageYOffset - navbarHeight - 20;

                window.scrollTo({
                    top: targetPosition,
                    behavior: 'smooth'
                });
            }
        });
    });
}

// ============================================
// STAGGERED ANIMATION FOR GRIDS
// ============================================

function initStaggeredAnimations() {
    const grids = document.querySelectorAll('.features-grid, .testimonials-grid, .pricing-grid');

    grids.forEach(function(grid) {
        const children = grid.children;
        Array.from(children).forEach(function(child, index) {
            child.style.transitionDelay = (index * 0.1) + 's';
        });
    });
}

// ============================================
// HERO CARD TYPING ANIMATION
// ============================================

function initTypingAnimation() {
    const typingElement = document.querySelector('.typing-animation');
    if (!typingElement) return;

    const texts = [
        'Analyzing submission...',
        'Evaluating thesis...',
        'Checking grammar...',
        'Generating feedback...'
    ];

    let textIndex = 0;

    setInterval(function() {
        textIndex = (textIndex + 1) % texts.length;
        typingElement.textContent = texts[textIndex];
    }, 3000);
}

// ============================================
// PARALLAX EFFECT FOR HERO
// ============================================

function initParallax() {
    const heroGlow = document.querySelector('.hero-glow');
    if (!heroGlow) return;

    let ticking = false;

    window.addEventListener('scroll', function() {
        if (!ticking) {
            window.requestAnimationFrame(function() {
                const scrolled = window.pageYOffset;
                heroGlow.style.transform = 'translateX(-50%) translateY(' + (scrolled * 0.3) + 'px)';
                ticking = false;
            });
            ticking = true;
        }
    }, { passive: true });
}

// ============================================
// PRELOADER / INITIAL ANIMATION
// ============================================

function initPageLoad() {
    // Add loaded class to body after a short delay
    setTimeout(function() {
        document.body.classList.add('loaded');
    }, 100);
}

// ============================================
// INITIALIZE EVERYTHING
// ============================================

document.addEventListener('DOMContentLoaded', function() {
    initPageLoad();
    initScrollAnimations();
    initSmoothScroll();
    initStaggeredAnimations();
    initTypingAnimation();
    initParallax();

    // Initial scroll check
    handleScroll();
});

// ============================================
// FORM INPUT ANIMATIONS
// ============================================

// Add focus/blur effects to form inputs
document.addEventListener('focusin', function(event) {
    if (event.target.matches('.form-group input')) {
        event.target.parentElement.classList.add('focused');
    }
});

document.addEventListener('focusout', function(event) {
    if (event.target.matches('.form-group input')) {
        event.target.parentElement.classList.remove('focused');
    }
});

// ============================================
// ACCESSIBILITY - Focus Trap in Modal
// ============================================

function trapFocus(element) {
    const focusableElements = element.querySelectorAll(
        'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
    );

    const firstFocusable = focusableElements[0];
    const lastFocusable = focusableElements[focusableElements.length - 1];

    element.addEventListener('keydown', function(event) {
        if (event.key !== 'Tab') return;

        if (event.shiftKey) {
            if (document.activeElement === firstFocusable) {
                lastFocusable.focus();
                event.preventDefault();
            }
        } else {
            if (document.activeElement === lastFocusable) {
                firstFocusable.focus();
                event.preventDefault();
            }
        }
    });
}

// Apply focus trap to modal when opened
const modalObserver = new MutationObserver(function(mutations) {
    mutations.forEach(function(mutation) {
        if (mutation.target.classList.contains('active')) {
            trapFocus(loginModal.querySelector('.modal'));
        }
    });
});

modalObserver.observe(loginModal, { attributes: true, attributeFilter: ['class'] });

// ============================================
// CONSOLE EASTER EGG
// ============================================

console.log('%c Graider ', 'background: linear-gradient(135deg, #6366f1, #8b5cf6); color: white; font-size: 24px; padding: 10px 20px; border-radius: 8px; font-weight: bold;');
console.log('%cAI-Powered Grading That Saves Teachers Hours', 'color: #6366f1; font-size: 14px;');
console.log('%cInterested in joining our team? Email: careers@graider.live', 'color: #6b7280; font-size: 12px;');
