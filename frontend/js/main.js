import { state } from './state.js';
import { api } from './api.js';
import { applyTranslations } from './i18n.js';
import { updateStats } from './utils.js';
import { loadPhotos, resetAndReload, setupInfiniteScroll } from './gallery.js';
import { loadTimeline, loadLocations, closeMobileSidebar, resetSidebarTimer } from './sidebar.js';
import { closeModal, renderModalContent } from './modal.js';

const $ = (id) => document.getElementById(id);

async function checkScanStatus() {
  try {
    const status = await api("/api/scan/status");
    const scanBanner = $("scan-banner");
    const loadingOverlay = $("loading-overlay");
    const scanBannerText = $("scan-banner-text");
    const scanBannerProgress = $("scan-banner-progress");
    const loadingText = $("loading-text");
    const loadingProgressBar = $("loading-progress-bar");

    if (status.status === "complete" || status.status === "idle") {
      if (scanBanner) scanBanner.classList.add("hidden");
      if (loadingOverlay) loadingOverlay.classList.add("hidden");

      if (!state.scanComplete) {
        state.scanComplete = true;
        state.currentPage = 1;
        await loadPhotos(false);
        await loadTimeline();
        await loadLocations();
        updateStats();
      }
      return;
    }

    if (status.status === "scanning" || status.status === "generating_thumbnails" || status.status === "geocoding") {
      if (scanBanner) scanBanner.classList.remove("hidden");
      if (scanBannerText) scanBannerText.textContent = status.message || status.status;

      let pct = 100;
      if (status.total > 0) {
        pct = Math.round((status.progress / status.total) * 100);
      }
      if (scanBannerProgress) scanBannerProgress.style.width = pct + "%";

      if (!state.scanComplete) {
        if (loadingOverlay) loadingOverlay.classList.remove("hidden");
        if (loadingText) loadingText.textContent = status.message || status.status;
        if (loadingProgressBar) loadingProgressBar.style.width = pct + "%";
      }

      setTimeout(checkScanStatus, 2000);

      if (status.progress > 100 && state.photos.length === 0) {
        state.currentPage = 1;
        loadPhotos(false);
      }
    }
  } catch (e) {
    setTimeout(checkScanStatus, 5000);
  }
}

function setupFilters() {
  const filterBtns = document.querySelectorAll(".filter-btn");
  filterBtns.forEach(function (btn) {
    if (btn.closest('#modal-info')) return; // Ignore buttons dynamically generated in modal
    btn.addEventListener("click", function () {
      document.querySelectorAll(".filter-group .filter-btn").forEach(b => b.classList.remove("active"));
      this.classList.add("active");
      const filter = this.dataset.filter;
      state.activeFilter = filter;
      resetAndReload();
      resetSidebarTimer();
    });
  });

  const dateFromInput = $("date-from");
  const dateToInput = $("date-to");
  const searchInput = $("search-input");
  
  if (dateFromInput) {
    dateFromInput.addEventListener("change", function () {
      state.dateFrom = this.value || null;
      resetAndReload();
    });
  }

  if (dateToInput) {
    dateToInput.addEventListener("change", function () {
      state.dateTo = this.value || null;
      resetAndReload();
    });
  }

  let searchTimeout;
  if (searchInput) {
    searchInput.addEventListener("input", function () {
      clearTimeout(searchTimeout);
      searchTimeout = setTimeout(function () {
        const val = searchInput.value.trim();
        state.activeLocation = val || null;
        state.activeCountry = null;
        resetAndReload();
      }, 400);
    });
  }

  const mobileMenuBtn = $("mobile-menu-btn");
  const sidebar = $("sidebar");
  const sidebarOverlay = $("sidebar-overlay");
  if (mobileMenuBtn && sidebar && sidebarOverlay) {
    mobileMenuBtn.addEventListener("click", function () {
      sidebar.classList.add("open");
      sidebarOverlay.classList.add("show");
      resetSidebarTimer();
    });
    sidebarOverlay.addEventListener("click", function () {
      closeMobileSidebar();
    });
  }

  const loadMoreBtn = $("load-more-btn");
  if (loadMoreBtn) {
    loadMoreBtn.addEventListener("click", function () {
      state.currentPage++;
      loadPhotos(true);
    });
  }
}

function setupKeyboard() {
  document.addEventListener("keydown", function (e) {
    if (state.modalPhotoIndex < 0) return;

    if (e.key === "Escape") {
      closeModal();
    } else if (e.key === "ArrowLeft") {
      e.preventDefault();
      if (state.modalPhotoIndex > 0) {
        state.modalPhotoIndex--;
        renderModalContent();
      }
    } else if (e.key === "ArrowRight") {
      e.preventDefault();
      if (state.modalPhotoIndex < state.photos.length - 1) {
        state.modalPhotoIndex++;
        renderModalContent();
      }
    }
  });

  const modalClose = $("modal-close");
  const modalPrev = $("modal-prev");
  const modalNext = $("modal-next");
  const modalBackdrop = $("modal-backdrop");
  const modalImageContainer = $("modal-image-container");

  if (modalClose) modalClose.addEventListener("click", closeModal);
  if (modalPrev) {
    modalPrev.addEventListener("click", function () {
      if (state.modalPhotoIndex > 0) {
        state.modalPhotoIndex--;
        renderModalContent();
      }
    });
  }
  if (modalNext) {
    modalNext.addEventListener("click", function () {
      if (state.modalPhotoIndex < state.photos.length - 1) {
        state.modalPhotoIndex++;
        renderModalContent();
      }
    });
  }
  if (modalBackdrop) {
    modalBackdrop.addEventListener("click", function (e) {
      if (e.target === modalBackdrop || e.target === modalImageContainer) {
        closeModal();
      }
    });
  }
}

async function init() {
  const langToggle = $("lang-toggle");
  const loadOriginalToggle = $("load-original-toggle");
  const themeToggle = $("theme-toggle");

  try {
    const config = await api("/api/config");
    
    if (localStorage.getItem("app_language")) {
        state.language = localStorage.getItem("app_language");
    } else if (config.language) {
        state.language = config.language;
    }
    if (langToggle) {
        if (state.language === "en") langToggle.classList.add("active");
        else langToggle.classList.remove("active");
    }

    if (localStorage.getItem("app_theme")) {
        state.theme = localStorage.getItem("app_theme");
    } else if (config.theme) {
        state.theme = config.theme;
    }
    
    if (themeToggle) {
        if (state.theme === "dark") themeToggle.classList.add("active");
        else themeToggle.classList.remove("active");
    }

    if (config.load_original_on_click !== undefined) {
        state.loadOriginalOnClick = config.load_original_on_click;
        if (loadOriginalToggle) {
            if (state.loadOriginalOnClick) loadOriginalToggle.classList.add("active");
            else loadOriginalToggle.classList.remove("active");
        }
    }
  } catch (e) {
    console.warn("Failed to load config, using defaults");
  }

  applyTranslations();
  document.body.className = "theme-" + state.theme;

  setupFilters();
  setupKeyboard();
  setupInfiniteScroll();

  if (loadOriginalToggle) {
    loadOriginalToggle.addEventListener("click", function (e) {
      this.classList.toggle("active");
      state.loadOriginalOnClick = this.classList.contains("active");
    });
  }

  if (langToggle) {
    langToggle.addEventListener("click", function (e) {
      this.classList.toggle("active");
      state.language = this.classList.contains("active") ? "en" : "zh";
      localStorage.setItem("app_language", state.language);
      applyTranslations();
      loadTimeline();
      loadLocations();
      resetAndReload();
    });
  }

  if (themeToggle) {
    themeToggle.addEventListener("click", function (e) {
      this.classList.toggle("active");
      state.theme = this.classList.contains("active") ? "dark" : "light";
      localStorage.setItem("app_theme", state.theme);
      document.body.className = "theme-" + state.theme;
    });
  }

  await checkScanStatus();

  if (state.scanComplete && state.photos.length === 0) {
    await loadPhotos(false);
    await loadTimeline();
    await loadLocations();
    updateStats();
  }
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", init);
} else {
  init();
}
