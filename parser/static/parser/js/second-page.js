document.addEventListener('DOMContentLoaded', function() {
  const goToMainPage = document.getElementById('goToMainPage');
  const toggleCheck = document.getElementById('togle-check');

  if (goToMainPage) {
    goToMainPage.onclick = function() {
      const mainPageUrlElement = document.getElementById('mainPageUrl');
      if (mainPageUrlElement && mainPageUrlElement.value) {
        window.location.href = mainPageUrlElement.value;
      } else {
        window.location.href = '/'; 
      }
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
    if (window.location.href.includes('/archived/')) {
      toggleCheck.checked = true;
    }
  }

  const mainPageContainer = document.querySelector('.main-page-container');
  if (mainPageContainer) {
    mainPageContainer.addEventListener('mouseenter', function() {
      this.style.opacity = '0.8';
    });
    mainPageContainer.addEventListener('mouseleave', function() {
      this.style.opacity = '1';
    });
  }

  const cardsContainer = document.getElementById('cardsContainer');
  const infiniteScrollTrigger = document.getElementById('infiniteScrollTrigger');
  const currentPageInput = document.getElementById('currentPage');
  const hasNextPageInput = document.getElementById('hasNextPage');
  const loadMoreUrlInput = document.getElementById('loadMoreUrl');

  if (!cardsContainer || !infiniteScrollTrigger || !currentPageInput || !hasNextPageInput || !loadMoreUrlInput) {
    console.warn("Infinite scroll: Essential elements not found. Infinite scroll disabled.");
    return;
  }

  let isLoading = false;

  const loadMoreInternships = () => {
    if (isLoading || hasNextPageInput.value !== 'true') {
      return;
    }
    isLoading = true;
    let nextPage = parseInt(currentPageInput.value) + 1;

    const filterForm = document.querySelector('.filter-card form');
    const formData = new FormData(filterForm);
    const params = new URLSearchParams(formData);
    params.set('page', nextPage.toString());
    const currentUrl = new URL(loadMoreUrlInput.value, window.location.origin);
    currentUrl.search = params.toString();

    fetch(currentUrl.href, {
      method: 'GET',
      headers: {
        'X-Requested-With': 'XMLHttpRequest',
      },
    })
    .then(response => {
      if (!response.ok) {
        console.error(`Infinite scroll: HTTP error! status: ${response.status}`);
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      return response.json();
    })
    .then(data => {
      if (data.html && data.html.trim().length > 0) {
        infiniteScrollTrigger.insertAdjacentHTML('beforebegin', data.html);
        currentPageInput.value = nextPage.toString();
        hasNextPageInput.value = data.has_next ? 'true' : 'false';
        setTimeout(() => {
          if (cardsContainer.scrollHeight <= cardsContainer.clientHeight && hasNextPageInput.value === 'true') {
            loadMoreInternships();
          }
        }, 100);
      } else {
        hasNextPageInput.value = 'false';
        infiniteScrollTrigger.style.display = 'none';
      }
      isLoading = false;
    })
    .catch(error => {
      console.error('Infinite scroll: Error loading internships:', error);
      isLoading = false;
    });
  };

  const observerOptions = {
    root: cardsContainer,
    rootMargin: '0px 0px 300px 0px',
    threshold: 0.01
  };

  const intersectionCallback = (entries) => {
    const entry = entries[0];
    if (!entry) return;

    if (entry.isIntersecting && !isLoading && hasNextPageInput.value === 'true') {
      loadMoreInternships();
    }
  };

  const observer = new IntersectionObserver(intersectionCallback, observerOptions);
  if (infiniteScrollTrigger) {
    observer.observe(infiniteScrollTrigger);
  } else {
    console.error("Infinite scroll: infiniteScrollTrigger element NOT FOUND. Observer not started.");
  }

  function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
  }
  const csrftoken = getCookie('csrftoken');

  cardsContainer.addEventListener('click', function(event) {
    const deleteButton = event.target.closest('.delete-internship-btn');
    if (deleteButton) {
      const internshipCard = deleteButton.closest('.company-card');
      const internshipId = internshipCard.dataset.internshipId;

      if (confirm('Вы уверены, что хотите удалить эту стажировку?')) {
        fetch(`/parser/delete_internship/${internshipId}/`, {
          method: 'DELETE',
          headers: {
            'X-CSRFToken': csrftoken,
            'Content-Type': 'application/json'
          }
        })
        .then(response => {
          if (response.ok) {
            internshipCard.remove();
          } else {
            alert('Ошибка при удалении стажировки.');
          }
        })
        .catch(error => {
          console.error('Ошибка:', error);
          alert('Ошибка при удалении стажировки.');
        });
      }
    }
  });

  setTimeout(() => {
    if (cardsContainer.scrollHeight <= cardsContainer.clientHeight && hasNextPageInput.value === 'true') {
      loadMoreInternships();
    }
  }, 500);
});