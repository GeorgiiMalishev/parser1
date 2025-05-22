document.addEventListener('DOMContentLoaded', function() {
  const goToMainPage = document.getElementById('goToMainPage');
  const toggleCheck = document.getElementById('togle-check');
  
  if (goToMainPage) {
    goToMainPage.onclick = function() {
      window.location.href = '/';
    };
  }
  
  if (toggleCheck) {
    toggleCheck.onchange = function() {
      if (this.checked) {
        window.location.href = '/parser/archived/';
      } else {
        window.location.href = '/parser/internships/';
      }
    };
    
    // Установка состояния переключателя в зависимости от текущего URL
    if (window.location.href.includes('/archived/')) {
      toggleCheck.checked = true;
    }
  }

  // Добавляем стили при наведении
  const mainPageContainer = document.querySelector('.main-page-container');
  if (mainPageContainer) {
    mainPageContainer.addEventListener('mouseenter', function() {
      this.style.opacity = '0.8';
    });
    
    mainPageContainer.addEventListener('mouseleave', function() {
      this.style.opacity = '1';
    });
  }
});