document.addEventListener("DOMContentLoaded", function () {
  const openModalBtn = document.getElementById("openModalSite");
  const modal = document.getElementById("modal");
  const addSiteBtn = document.getElementById("onAddSiteClick");
  const insideModal = document.getElementById("insideModal");
  const companyContainer = document.getElementById('companyContainer');
  const closeLooked = document.getElementById('closeLooked');

  const fetchInternshipDataBtn = document.getElementById("fetchInternshipDataBtn");
  const loadingIndicator = document.getElementById("loadingIndicator");
  const confirmAndSaveInternshipBtn = document.getElementById("confirmAndSaveInternshipBtn");
  
  const siteNameInput = document.getElementById("siteNameInput");
  const siteUrlInput = document.getElementById("siteUrlInput");

  const internshipCompanyInput = document.getElementById("internshipCompany");
  const internshipPositionInput = document.getElementById("internshipPosition");
  const internshipStartDateInput = document.getElementById("internshipStartDate");
  const internshipEndDateInput = document.getElementById("internshipEndDate");
  const internshipTechnologiesInput = document.getElementById("internshipTechnologies");
  const internshipDescriptionEl = document.getElementById("internshipDescription"); // Это textarea, используем .value

  const notificationElement = document.getElementById("customNotification");
  const notificationMessageElement = document.getElementById("customNotificationMessage");
  let notificationTimeout;

  const openSpecialParsersSettingsModalBtn = document.getElementById("openSpecialParsersSettingsModal");
  const specialParsersSettingsModal = document.getElementById("specialParsersSettingsModal");
  const keywordsInput = document.getElementById("keywordsInput");
  const citiesInput = document.getElementById("citiesInput");
  const saveSpecialParsersSettingsBtn = document.getElementById("saveSpecialParsersSettingsBtn");
  const specialSettingsLoadingIndicator = document.getElementById("specialSettingsLoadingIndicator");

  const jsConfigDiv = document.getElementById('js-config');
  const previewUrl = jsConfigDiv.dataset.previewUrl;
  const createSiteUrl = jsConfigDiv.dataset.websiteCreateUrl;
  const deleteSiteBaseUrl = jsConfigDiv.dataset.websiteDeleteUrl.replace('/0/', '/'); // Получаем базовый URL
  const getSpecialSettingsUrl = jsConfigDiv.dataset.getSpecialSettingsUrl; 
  const saveSpecialSettingsUrl = jsConfigDiv.dataset.saveSpecialSettingsUrl;

  let tempSiteName = "";
  let tempSiteUrl = "";
  let originalPreviewData = {}; // Для хранения оригинальных данных от preview

  function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== "") {
      const cookies = document.cookie.split(";");
      for (let i = 0; i < cookies.length; i++) {
        const cookie = cookies[i].trim();
        if (cookie.substring(0, name.length + 1) === name + "=") {
          cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
          break;
        }
      }
    }
    return cookieValue;
  }
  const csrftoken = getCookie("csrftoken");

  function showCustomNotification(message, type = 'success') { // type может быть 'success' или 'error'
    if (!notificationElement || !notificationMessageElement) return;

    clearTimeout(notificationTimeout); // Очищаем предыдущий таймаут, если есть

    notificationMessageElement.textContent = message;
    notificationElement.className = 'custom-notification'; // Сбрасываем классы
    notificationElement.classList.add(type); // Добавляем класс success или error
    notificationElement.classList.add('show');

    notificationTimeout = setTimeout(() => {
      notificationElement.classList.remove('show');
      // Можно добавить небольшую задержку перед полным скрытием, чтобы анимация успела отработать
      // setTimeout(() => { notificationElement.className = 'custom-notification'; }, 500);
    }, 5000); // Уведомление будет видно 5 секунд
  }

  if (fetchInternshipDataBtn) {
    fetchInternshipDataBtn.onclick = function () {
      const siteUrl = siteUrlInput.value.trim();
      if (!siteUrl) {
        showCustomNotification("Пожалуйста, введите URL сайта.", "error");
        return;
      }
      // Простая валидация URL
      try {
        new URL(siteUrl);
      } catch (_) {
        showCustomNotification("Пожалуйста, введите корректный URL сайта (например, http://example.com).", "error");
        return;
      }


      tempSiteName = siteNameInput.value.trim();
      tempSiteUrl = siteUrl;

      loadingIndicator.style.display = "block";
      fetchInternshipDataBtn.disabled = true;
      fetchInternshipDataBtn.style.display = "none"; // Скрываем кнопку

      fetch(previewUrl, { // Используем URL из js-config
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrftoken,
        },
        body: JSON.stringify({ url: siteUrl }),
      })
      .then(response => {
        if (!response.ok) {
          // Если ответ не успешный (например, 4xx, 5xx)
          return response.text().then(text => {
            // Попытаемся извлечь JSON, если это ошибка API в JSON формате
            try {
              const errData = JSON.parse(text);
              throw new Error(errData.error || errData.detail || `Ошибка сервера: ${response.status}`);
            } catch (e) {
              // Если это не JSON (вероятно, HTML страница ошибки)
              throw new Error(`Ошибка сервера: ${response.status}. Ответ не JSON: ${text.substring(0, 200)}...`);
            }
          });
        }
        // Проверяем Content-Type перед парсингом JSON
        const contentType = response.headers.get("content-type");
        if (contentType && contentType.indexOf("application/json") !== -1) {
            return response.json();
        } else {
            return response.text().then(text => {
                throw new Error(`Ответ сервера не является JSON. Получено: ${text.substring(0, 200)}...`);
            });
        }
      })
      .then(data => {
        originalPreviewData = data; // Сохраняем все полученные данные
        loadingIndicator.style.display = "none";
        fetchInternshipDataBtn.disabled = false;
        fetchInternshipDataBtn.style.display = "block"; // Показываем кнопку

        // Заполняем поля предпросмотра, проверяя наличие данных
        internshipCompanyInput.value = data.company || "";
        internshipPositionInput.value = data.position || data.title || "";
        internshipStartDateInput.value = data.start_date || "";
        internshipEndDateInput.value = data.end_date || "";
        internshipTechnologiesInput.value = Array.isArray(data.technologies) ? data.technologies.join(", ") : (data.technologies || "");
        internshipDescriptionEl.value = data.description || "Описание отсутствует."; // Используем .value для textarea
        
        // Добавляем поля, которые могут отсутствовать в текущем HTML, но могут прийти от парсера
        // Например, salary, schedule, format и т.д.
        // Здесь можно динамически создать элементы или иметь скрытые поля в HTML

        insideModal.style.display = "none";
        companyContainer.style.display = "block";
      })
      .catch(error => {
        loadingIndicator.style.display = "none";
        fetchInternshipDataBtn.disabled = false;
        fetchInternshipDataBtn.style.display = "block"; // Показываем кнопку
        console.error("Ошибка при получении данных о стажировке:", error);
        showCustomNotification("Не удалось получить данные о стажировке: " + error.message, "error");
      });
    };
  }

  if (confirmAndSaveInternshipBtn) {
    confirmAndSaveInternshipBtn.onclick = function () {
      let siteNameToSave = tempSiteName; // tempSiteName хранит ввод пользователя или ""

      // Если пользователь не указал имя сайта, и у нас есть данные предпросмотра с заголовком
      if (!siteNameToSave && originalPreviewData && originalPreviewData.title) {
        siteNameToSave = originalPreviewData.title.trim();
      }
      // Если и после этого siteNameToSave пуст (пользователь не ввел, и в preview нет title),
      // то сработает серверная валидация "Имя и URL сайта обязательны", что соответствует текущему поведению.

      const payload = {
          name: siteNameToSave, // Используем имя сайта (возможно, автоматически заполненное)
          url: tempSiteUrl,
          title: originalPreviewData.title || internshipPositionInput.value.trim(), // Берем title из originalPreviewData, или position если title не было
          position: internshipPositionInput.value.trim(),
          company: internshipCompanyInput.value.trim(), 
          start_date: internshipStartDateInput.value || null,
          end_date: internshipEndDateInput.value || null,
          technologies: internshipTechnologiesInput.value.split(",").map(s => s.trim()).filter(s => s),
          description: internshipDescriptionEl.value.trim(), // Используем .value для textarea
          // Другие поля из originalPreviewData, которые не редактируются, но нужны для сохранения (например, city, salary)
          city: originalPreviewData.city || null, 
          salary: originalPreviewData.salary || null,
          // employment_type: originalPreviewData.employment_type || null, // Если есть
          // duration: originalPreviewData.duration || null, // Если есть
      };

      fetch(createSiteUrl, { // Используем URL из js-config
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrftoken,
        },
        body: JSON.stringify(payload),
      })
      .then(response => {
        if (!response.ok) {
          // Если это HTML ответ (например, редирект с ошибкой формы), то .json() упадет
          if (response.headers.get("content-type")?.includes("application/json")) {
            return response.json().then(err => { 
              let errorMessage = "Ошибка при сохранении.";
              if (err.detail) errorMessage = err.detail;
              else if (typeof err === 'object' && err !== null) errorMessage = Object.entries(err).map(([key, value]) => `${key}: ${Array.isArray(value) ? value.join(', ') : value}`).join('\n');
              throw new Error(errorMessage);
            });
          } else {
             return response.text().then(text => { throw new Error(`Ошибка сервера: ${response.status}. Ответ: ${text.substring(0,100)}`) });
          }
        }
        return { success: true, message: 'Сайт и стажировка успешно сохранены' }; 
      })
      .then(data => {
        showCustomNotification(data.message, "success");
        companyContainer.style.display = "none";
        modal.style.display = "none";
        siteNameInput.value = "";
        siteUrlInput.value = "";
      })
      .catch(error => {
        console.error("Ошибка при сохранении сайта и стажировки:", error);
        showCustomNotification("Не удалось сохранить сайт и стажировку: " + error.message, "error");
      });
    };
  }


  if (addSiteBtn) {
    addSiteBtn.onclick = function () {
      siteNameInput.value = "";
      siteUrlInput.value = "";
      fetchInternshipDataBtn.disabled = false;
      loadingIndicator.style.display = "none";
      companyContainer.style.display = "none";
      insideModal.style.display = "block";
    };
  }
  
  if (openModalBtn) {
    openModalBtn.onclick = function () {
      modal.style.display = "block";
      insideModal.style.display = "none";
      companyContainer.style.display = "none";
      specialParsersSettingsModal.style.display = "none";
      applyTextAdjustments();
    };
  }
  
  if (closeLooked) {
    closeLooked.onclick = function () {
      companyContainer.style.display = "none";
    };
  }

  modal.addEventListener('click', function(event) {
    if (event.target.classList.contains('delete-website-icon')) {
      const websiteId = event.target.dataset.websiteId;
      if (confirm('Вы уверены, что хотите удалить этот сайт и все связанные с ним стажировки?')) {
        fetch(`${deleteSiteBaseUrl}${websiteId}/`, {
          method: "DELETE",
          headers: {
            "X-CSRFToken": csrftoken,
            "Content-Type": "application/json"
          },
        })
        .then(response => {
          if (response.ok) {
            return response.json();
          }
          return response.json().then(err => { throw new Error(err.error || 'Ошибка удаления'); });
        })
        .then(data => {
          showCustomNotification(data.message, "success");
          event.target.closest('.site-card').remove();
        })
        .catch(error => {
          showCustomNotification("Ошибка: " + error.message, "error");
          console.error("Ошибка при удалении сайта:", error);
        });
      }
    }
  });

  window.onclick = function (event) {
    if (event.target === modal) {
      if (insideModal.style.display === "block") {
        insideModal.style.display = "none";
      } else if (companyContainer.style.display === "block") {
        companyContainer.style.display = "none";
      } else {
        modal.style.display = "none";
      }
    }

    if (event.target === insideModal) {
      insideModal.style.display = "none";
      companyContainer.style.display = "none";
    }

    if (event.target === specialParsersSettingsModal) {
      specialParsersSettingsModal.style.display = "none";
    }
  };

  function adjustElementText(element) {
    if (!element) return;

    const computedStyle = window.getComputedStyle(element);
    const originalFontSize = parseFloat(computedStyle.fontSize);
    if (isNaN(originalFontSize) || originalFontSize <= 0) return;

    element.style.fontSize = originalFontSize + 'px'; 
    element.style.whiteSpace = 'nowrap';
    element.style.overflow = 'hidden';
    element.style.textOverflow = 'clip'; 

    let currentFontSize = originalFontSize;
    const minAllowedFontSize = originalFontSize * 0.7; 
    const step = 0.5;

    if (element.scrollWidth <= element.clientWidth) {
        element.style.textOverflow = 'clip';
        return;
    }

    while (element.scrollWidth > element.clientWidth && currentFontSize > minAllowedFontSize) {
        currentFontSize -= step;
        if (currentFontSize < minAllowedFontSize) {
            currentFontSize = minAllowedFontSize;
        }
        element.style.fontSize = currentFontSize + 'px';
        if (element.scrollWidth <= element.clientWidth) {
            break;
        }
    }
    
    if (element.scrollWidth > element.clientWidth) {
        element.style.textOverflow = 'ellipsis';
    } else {
        element.style.textOverflow = 'clip';
    }
}

  function applyTextAdjustments() {
    const siteCards = modal.querySelectorAll('.site-card');
    siteCards.forEach(card => {
      const titleElement = card.querySelector('.card-title');
      const linkElement = card.querySelector('.card-link');

      if (titleElement) {
        adjustElementText(titleElement);
      }
      if (linkElement) {
        adjustElementText(linkElement);
      }
    });
  }

  if (openSpecialParsersSettingsModalBtn) {
    openSpecialParsersSettingsModalBtn.onclick = function() {
      specialSettingsLoadingIndicator.style.display = 'block';
      fetch(getSpecialSettingsUrl, {
        method: "GET",
        headers: {
          "X-CSRFToken": csrftoken,
          "Content-Type": "application/json"
        }
      })
      .then(response => {
        if (!response.ok) {
          return response.json().then(err => { throw new Error(err.error || 'Ошибка загрузки настроек'); });
        }
        return response.json();
      })
      .then(data => {
        keywordsInput.value = data.keywords ? data.keywords.join(', ') : ''; 
        citiesInput.value = data.cities ? data.cities.join(', ') : '';
        specialSettingsLoadingIndicator.style.display = 'none';
        specialParsersSettingsModal.style.display = 'block';
      })
      .catch(error => {
        specialSettingsLoadingIndicator.style.display = 'none';
        showCustomNotification("Ошибка загрузки настроек: " + error.message, "error");
        console.error("Ошибка при загрузке настроек особых парсеров:", error);
        keywordsInput.value = '';
        citiesInput.value = '';
        specialParsersSettingsModal.style.display = 'block'; 
      });
    };
  }

  if (saveSpecialParsersSettingsBtn) {
    saveSpecialParsersSettingsBtn.onclick = function() {
      const processTextareaValue = (value) => {
        return value.split(',')
                    .map(item => item.trim())
                    .filter(item => item);
      };

      const keywords = processTextareaValue(keywordsInput.value);
      const cities = processTextareaValue(citiesInput.value);

      if (keywords.length === 0) {
        showCustomNotification("Пожалуйста, введите хотя бы одно ключевое слово.", "error");
        return;
      }

      specialSettingsLoadingIndicator.style.display = 'block';
      saveSpecialParsersSettingsBtn.disabled = true;

      fetch(saveSpecialSettingsUrl, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrftoken,
        },
        body: JSON.stringify({ keywords: keywords, cities: cities }),
      })
      .then(response => {
        if (!response.ok) {
            return response.json().then(err => { 
                let errorMessage = "Ошибка при сохранении настроек.";
                if (err.detail) errorMessage = err.detail;
                else if (err.error) errorMessage = err.error;
                else if (typeof err === 'object' && err !== null) errorMessage = Object.entries(err).map(([key, value]) => `${key}: ${Array.isArray(value) ? value.join(', ') : value}`).join('\n');
                throw new Error(errorMessage);
            });
        }
        return response.json(); 
      })
      .then(data => {
        showCustomNotification(data.message || "Настройки успешно сохранены и парсинг запущен.", "success");
        specialParsersSettingsModal.style.display = 'none';
      })
      .catch(error => {
        showCustomNotification("Не удалось сохранить настройки: " + error.message, "error");
        console.error("Ошибка при сохранении настроек особых парсеров:", error);
      })
      .finally(() => {
        specialSettingsLoadingIndicator.style.display = 'none';
        saveSpecialParsersSettingsBtn.disabled = false;
      });
    };
  }
});