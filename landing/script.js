/* ============================================
   GRAIDER LANDING PAGE - JAVASCRIPT
   ============================================ */

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
    const email = document.getElementById('login-email').value;
    const password = document.getElementById('login-password').value;

    // Basic validation
    if (!email || !password) {
        showFormError('Please fill in all fields');
        return;
    }

    // Show loading state
    const submitBtn = event.target.querySelector('button[type="submit"]');
    const originalText = submitBtn.textContent;
    submitBtn.textContent = 'Signing in...';
    submitBtn.disabled = true;

    // Simulate API call - replace with actual API integration
    setTimeout(function() {
        // For demo, redirect to app
        window.location.href = '/';
    }, 1500);
}

function handleSignup(event) {
    event.preventDefault();
    const firstName = document.getElementById('signup-first').value;
    const lastName = document.getElementById('signup-last').value;
    const email = document.getElementById('signup-email').value;
    const password = document.getElementById('signup-password').value;
    const terms = document.getElementById('terms').checked;

    // Basic validation
    if (!firstName || !lastName || !email || !password) {
        showFormError('Please fill in all fields');
        return;
    }

    if (password.length < 8) {
        showFormError('Password must be at least 8 characters');
        return;
    }

    if (!terms) {
        showFormError('Please accept the terms and conditions');
        return;
    }

    // Show loading state
    const submitBtn = event.target.querySelector('button[type="submit"]');
    const originalText = submitBtn.textContent;
    submitBtn.textContent = 'Creating account...';
    submitBtn.disabled = true;

    // Simulate API call - replace with actual API integration
    setTimeout(function() {
        // For demo, redirect to app
        window.location.href = '/';
    }, 1500);
}

function handleForgotPassword(event) {
    event.preventDefault();
    const email = document.getElementById('forgot-email').value;

    if (!email) {
        showFormError('Please enter your email');
        return;
    }

    // Show loading state
    const submitBtn = event.target.querySelector('button[type="submit"]');
    submitBtn.textContent = 'Sending...';
    submitBtn.disabled = true;

    // Simulate API call
    setTimeout(function() {
        submitBtn.textContent = 'Link Sent!';
        submitBtn.style.background = '#22c55e';

        setTimeout(function() {
            showLoginForm();
            submitBtn.textContent = 'Send Reset Link';
            submitBtn.style.background = '';
            submitBtn.disabled = false;
        }, 2000);
    }, 1500);
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
