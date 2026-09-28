const menuButton = document.querySelector('.menu-button');
const nav = document.querySelector('.main-nav');
const checkInButton = document.querySelector('#check-in');
const checkInMessage = document.querySelector('#check-in-message');

// Toggle navigation menu
menuButton.addEventListener('click', () => {
  const isOpen = menuButton.getAttribute('aria-expanded') === 'true';
  menuButton.setAttribute('aria-expanded', String(!isOpen));
  menuButton.setAttribute('aria-label', isOpen ? 'Open navigation' : 'Close navigation');
  menuButton.querySelector('.menu-label').textContent = isOpen ? 'Menu' : 'Close';
  nav.classList.toggle('is-open', !isOpen);
});


// Handle check-in button click
checkInButton.addEventListener('click', () => {
  checkInMessage.textContent = 'Check-in saved. A pause is already progress.';
  checkInButton.querySelector('span').textContent = '✓';
  checkInButton.disabled = true;
});

// Close navigation menu when a link is clicked
document.querySelectorAll('.main-nav a').forEach((link) => {
  link.addEventListener('click', () => {
    nav.classList.remove('is-open');
    menuButton.setAttribute('aria-expanded', 'false');
    menuButton.setAttribute('aria-label', 'Open navigation');
    menuButton.querySelector('.menu-label').textContent = 'Menu';
  });
});
