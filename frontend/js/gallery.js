import { state } from './state.js';
import { api } from './api.js';
import { t } from './i18n.js';
import { $, formatDateLabel, formatDuration, createEmptyState } from './utils.js';
import { openModal } from './modal.js';

let galleryObserver = null;

function initVirtualization() {
  if (galleryObserver) {
    galleryObserver.disconnect();
  }
  
  galleryObserver = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      const card = entry.target;
      const photoId = card.dataset.id;
      const photo = state.photos.find(p => p.id.toString() === photoId);
      if (!photo) return;

      if (entry.isIntersecting) {
        if (!card.hasAttribute('data-rendered')) {
          renderCardContent(card, photo);
          card.setAttribute('data-rendered', 'true');
        }
      } else {
        if (card.hasAttribute('data-rendered')) {
          // Unload DOM elements to save memory (DOM Virtualization)
          card.replaceChildren();
          card.removeAttribute('data-rendered');
        }
      }
    });
  }, {
    root: $('gallery-container'),
    rootMargin: '600px 0px', // Buffer zone to prevent flashing
    threshold: 0
  });
}

function renderCardContent(card, photo) {
  const img = document.createElement("img");
  img.className = "loading";
  img.alt = photo.filename || "照片";
  img.src = "/api/photos/" + photo.id + "/thumbnail/small?v=" + Date.now();
  img.onload = () => img.className = "loaded";
  img.onerror = () => {
    img.className = "loaded";
    img.style.backgroundColor = "var(--bg-tertiary)";
  };
  card.appendChild(img);

  const overlay = document.createElement("div");
  overlay.className = "photo-card-overlay";

  if (photo.is_live_photo) {
    const badge = document.createElement("span");
    badge.className = "photo-card-badge live";
    badge.textContent = "LIVE";
    overlay.appendChild(badge);
  } else if (photo.file_type === "MOV") {
    const badge = document.createElement("span");
    badge.className = "photo-card-badge video";
    const dur = photo.duration ? formatDuration(photo.duration) : t("video_dur");
    badge.textContent = dur;
    overlay.appendChild(badge);
  }

  if (photo.location_name) {
    const locBadge = document.createElement("span");
    locBadge.className = "photo-card-badge";
    locBadge.textContent = "📍";
    overlay.appendChild(locBadge);
  }

  card.appendChild(overlay);

  if (photo.is_live_photo && photo.live_photo_mov) {
    let hoverTimeout;
    card.addEventListener("mouseenter", function () {
      hoverTimeout = setTimeout(() => {
        if (!card.querySelector("video")) {
          const video = document.createElement("video");
          video.muted = true;
          video.loop = true;
          video.playsInline = true;
          video.src = "/api/photos/" + photo.id + "/live-video";
          video.play().catch(function () {});
          card.appendChild(video);
        } else {
          const v = card.querySelector("video");
          if (v) v.play().catch(function () {});
        }
      }, 200);
    });

    card.addEventListener("mouseleave", function () {
      clearTimeout(hoverTimeout);
      const v = card.querySelector("video");
      if (v) {
        v.pause();
        v.removeAttribute("src");
        v.load();
        v.remove();
      }
    });
  }
}

function createPhotoCard(photo) {
  const card = document.createElement("div");
  card.className = "photo-card";
  card.setAttribute("data-id", photo.id);
  
  card.addEventListener("click", function () {
    const idx = state.photos.findIndex(function (p) { return p.id === photo.id; });
    if (idx >= 0) {
      openModal(idx);
    }
  });

  if (galleryObserver) {
    galleryObserver.observe(card);
  } else {
    renderCardContent(card, photo);
  }

  return card;
}

function groupByDate(photos) {
  const groups = {};
  for (const photo of photos) {
    const date = photo.taken_at ? photo.taken_at.split("T")[0] : t("unknown_date");
    if (!groups[date]) {
      groups[date] = [];
    }
    groups[date].push(photo);
  }
  return groups;
}

function getNewPhotos() {
  const start = (state.currentPage - 1) * state.perPage;
  return state.photos.slice(start);
}

export function renderGallery(append) {
  const gallery = $("gallery");
  if (!append) {
    gallery.replaceChildren();
    if (galleryObserver) galleryObserver.disconnect();
    initVirtualization();
  }

  if (state.photos.length === 0) {
    const emptyEl = createEmptyState("📷", t("no_photos"), t("adjust_filters"));
    gallery.appendChild(emptyEl);
    return;
  }

  const groups = groupByDate(append ? getNewPhotos() : state.photos);

  for (const [date, photos] of Object.entries(groups)) {
    let groupEl = append ? gallery.querySelector(`[data-date="${CSS.escape(date)}"]`) : null;
    let gridEl;

    if (!groupEl) {
      groupEl = document.createElement("div");
      groupEl.className = "gallery-date-group";
      groupEl.setAttribute("data-date", date);

      const label = document.createElement("div");
      label.className = "gallery-date-label";
      
      let locText = "";
      const locationSets = {};
      for (const photo of photos) {
          if (!photo.display_location) continue;
          const partsDisp = photo.display_location.split(", ");
          if (partsDisp.length < 2) continue;
          
          let country = partsDisp[partsDisp.length - 1].trim();
          let city = partsDisp[0];
          if (city.includes(" (")) city = city.split(" (")[0];
          if (city.includes(" / ")) city = city.split(" / ")[0];
          if (state.language === "zh" && (city.toLowerCase() === "zuerich" || city === "Zurich")) {
              city = "苏黎世";
          } else if (state.language === "en" && (city.toLowerCase() === "zuerich" || city === "苏黎世")) {
              city = "Zurich";
          }
          city = city.trim();

          if (!locationSets[country]) locationSets[country] = new Set();
          locationSets[country].add(city);
      }
      
      const locStrings = [];
      for (const [country, citiesSet] of Object.entries(locationSets)) {
          const cities = Array.from(citiesSet);
          if (cities.length > 0) {
              locStrings.push(`${country} (${cities.join(", ")})`);
          } else {
              locStrings.push(country);
          }
      }
      if (locStrings.length > 0) {
          locText = " - " + locStrings.join(" | ");
      }

      label.textContent = formatDateLabel(date) + locText;
      groupEl.appendChild(label);

      gridEl = document.createElement("div");
      gridEl.className = "gallery-grid";
      groupEl.appendChild(gridEl);

      gallery.appendChild(groupEl);
    } else {
      gridEl = groupEl.querySelector(".gallery-grid");
    }

    for (const photo of photos) {
      const card = createPhotoCard(photo);
      gridEl.appendChild(card);
    }
  }
}

export function updateLoadMoreButton() {
  const loadMoreContainer = $("load-more-container");
  if (state.currentPage < state.totalPages) {
    loadMoreContainer.style.display = "";
  } else {
    loadMoreContainer.style.display = "none";
  }
}

export async function loadPhotos(append) {
  if (state.loading) return;
  state.loading = true;

  const gallery = $("gallery");
  if (!append) {
    gallery.replaceChildren();
    const loadingEl = document.createElement("div");
    loadingEl.className = "gallery-loading";
    loadingEl.style.padding = "var(--space-2xl)";
    loadingEl.style.textAlign = "center";
    loadingEl.style.color = "var(--text-muted)";
    loadingEl.textContent = "⏳ " + t("loading");
    gallery.appendChild(loadingEl);
  }

  const params = new URLSearchParams();
  params.set("page", state.currentPage.toString());
  params.set("per_page", state.perPage.toString());

  if (state.activeFilter !== "all") {
    if (state.activeFilter === "PNG") {
      params.set("screenshots", "true");
    } else {
      params.set("file_type", state.activeFilter);
    }
  }

  if (state.activeLocation) params.set("location", state.activeLocation);
  if (state.activeCountry) params.set("country", state.activeCountry);
  if (state.activeCity) params.set("city", state.activeCity);
  if (state.dateFrom) params.set("date_from", state.dateFrom + "T00:00:00");
  if (state.dateTo) params.set("date_to", state.dateTo + "T23:59:59");
  if (state.language) params.set("lang", state.language);

  try {
    const data = await api("/api/photos?" + params.toString());
    if (append) {
      state.photos = state.photos.concat(data.photos);
    } else {
      state.photos = data.photos;
    }
    state.total = data.total;
    state.totalPages = data.pages;

    renderGallery(append);
    updateLoadMoreButton();
  } catch (e) {
    if (!append) {
      gallery.replaceChildren();
      const emptyEl = createEmptyState("⚠️", t("failed_load"), t("try_again"));
      gallery.appendChild(emptyEl);
    }
  }

  state.loading = false;
}

export function resetAndReload() {
  state.currentPage = 1;
  state.photos = [];
  loadPhotos(false);
}

export function setupInfiniteScroll() {
  const galleryContainer = $("gallery-container");
  galleryContainer.addEventListener("scroll", function () {
    if (state.loading || state.currentPage >= state.totalPages) return;
    const scrollBottom = galleryContainer.scrollHeight - galleryContainer.scrollTop - galleryContainer.clientHeight;
    if (scrollBottom < 800) { // increased threshold slightly for smoother scroll
      state.currentPage++;
      loadPhotos(true);
    }
  });
}
