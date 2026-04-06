// Stock-py Navigation and Common Setup
document.addEventListener('DOMContentLoaded', function() {
    // Update nav links to show active state based on current page
    const currentPage = window.location.pathname.split('/').pop() || 'dashboard.html';
    
    document.querySelectorAll('.navbar-nav .nav-link').forEach(link => {
        const href = link.getAttribute('href');
        if (href === currentPage || (currentPage === '' && href === 'dashboard.html')) {
            link.classList.add('active');
            if (link.parentElement.classList.contains('dropdown')) {
                link.parentElement.classList.add('active');
            }
        }
    });
});

// Mobile menu toggle
function setupNavbar() {
    const navbarToggler = document.querySelector('.navbar-toggler');
    const navbarMenu = document.getElementById('navbar-menu');
    
    if (navbarToggler && navbarMenu) {
        navbarToggler.addEventListener('click', () => {
            navbarMenu.classList.toggle('show');
        });
    }
}

// Initialize on load
document.addEventListener('DOMContentLoaded', setupNavbar);