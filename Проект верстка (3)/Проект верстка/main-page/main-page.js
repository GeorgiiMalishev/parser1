document.addEventListener("DOMContentLoaded", function () {
  const openModalBtn = document.getElementById("openModalSite");
  const modal = document.getElementById("modal");
  const addSiteBtn = document.getElementById("onAddSiteClick");
  const insideModal = document.getElementById("insideModal");
  const agreeBtn = document.getElementById("agreeBtn");
  const companyContainer = document.getElementById('companyContainer');
  const closeLooked = document.getElementById('closeLooked');
  
  agreeBtn.onclick = function () {
    insideModal.style.display = "none";
    companyContainer.style.display = "block";
  };

  addSiteBtn.onclick = function () {
    insideModal.style.display = "block";
  };
  openModalBtn.onclick = function () {
    modal.style.display = "block";
  };
  closeLooked.onclick = function () {
    companyContainer.style.display = "none";
  };

  window.onclick = function (event) {
    if (event.target === modal) {
      modal.style.display = "none";
    }
  };
});