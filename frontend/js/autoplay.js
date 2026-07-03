import { state } from './state.js';
import { $ } from './utils.js';
import { resetAndReload, loadPhotos } from './gallery.js';
import { openModal, closeModal, renderModalContent } from './modal.js';

let autoplayTimer = null;
let isAutoplaying = false;

export function initAutoplay() {
  const btn = $('autoplay-btn');
  const modal = $('autoplay-config-modal');
  const cancelBtn = $('autoplay-cancel-btn');
  const startBtn = $('autoplay-start-btn');
  const stopBtn = $('autoplay-stop-btn');
  
  if (btn) {
    btn.addEventListener('click', openAutoplayConfig);
  }
  
  if (cancelBtn) {
    cancelBtn.addEventListener('click', () => {
      modal.style.display = 'none';
    });
  }
  
  if (startBtn) {
    startBtn.addEventListener('click', startAutoplay);
  }

  if (stopBtn) {
    stopBtn.addEventListener('click', stopAutoplay);
  }
}

function openAutoplayConfig() {
  const modal = $('autoplay-config-modal');
  
  // Pre-fill dates
  $('autoplay-date-from').value = state.dateFrom || "";
  $('autoplay-date-to').value = state.dateTo || "";
  
  // Pre-fill locations
  const locSelect = $('autoplay-location');
  // keep the "All Locations" option
  locSelect.innerHTML = '<option value="">All Locations</option>';
  for (const loc of state.locations) {
    const option = document.createElement('option');
    option.value = loc.location_name;
    option.textContent = `${loc.display_location} (${loc.count})`;
    if (state.activeLocation === loc.location_name) {
      option.selected = true;
    }
    locSelect.appendChild(option);
  }
  
  // Pre-fill type based on current active filter
  const isAll = state.activeFilter === "all";
  $('autoplay-type-photo').checked = isAll || state.activeFilter.includes("HEIC");
  $('autoplay-type-video').checked = isAll || state.activeFilter.includes("MOV");
  $('autoplay-type-screenshot').checked = isAll || state.activeFilter.includes("PNG") || state.activeFilter === "PNG";
  
  modal.style.display = 'flex';
}

async function startAutoplay() {
  $('autoplay-config-modal').style.display = 'none';
  
  // Update state filters
  const dateFrom = $('autoplay-date-from').value;
  const dateTo = $('autoplay-date-to').value;
  state.dateFrom = dateFrom ? dateFrom : null;
  state.dateTo = dateTo ? dateTo : null;
  
  const loc = $('autoplay-location').value;
  state.activeLocation = loc ? loc : null;
  
  const wantsPhoto = $('autoplay-type-photo').checked;
  const wantsVideo = $('autoplay-type-video').checked;
  const wantsScreenshot = $('autoplay-type-screenshot').checked;
  
  let types = [];
  if (wantsPhoto) types.push("HEIC", "JPG");
  if (wantsVideo) types.push("MOV");
  if (wantsScreenshot) types.push("PNG");
  
  if (types.length === 0) types = ["NONE"]; // if user unchecked all
  
  // Instead of 'all', we construct a comma-separated list
  if (wantsPhoto && wantsVideo && wantsScreenshot) {
     state.activeFilter = "all";
  } else if (types.includes("PNG") && types.length === 1) {
     state.activeFilter = "PNG"; // The screenshot logic checks for "PNG" specifically
  } else {
     state.activeFilter = types.join(",");
  }
  
  // Reset gallery to match these new filters
  state.currentPage = 1;
  state.photos = [];
  const gallery = $('gallery');
  if (gallery) {
      gallery.replaceChildren();
      const loadingEl = document.createElement("div");
      loadingEl.style.padding = "40px";
      loadingEl.style.textAlign = "center";
      loadingEl.style.color = "var(--text-muted)";
      loadingEl.textContent = "⏳ Preparing slideshow...";
      gallery.appendChild(loadingEl);
  }
  
  isAutoplaying = true;
  $('autoplay-controls').style.display = 'block';
  
  // Load first page
  await loadPhotos(false);
  
  if (state.photos.length > 0) {
    openModal(0);
    autoplayLoop();
  } else {
    stopAutoplay();
    alert("No photos found for the selected criteria.");
  }
}

async function autoplayLoop() {
  if (!isAutoplaying) return;
  if (state.modalPhotoIndex === -1) {
    stopAutoplay();
    return;
  }
  
  if (state.modalPhotoIndex >= state.photos.length - 1) {
    // Reached the end of current page
    if (state.currentPage < state.totalPages) {
      state.currentPage++;
      await loadPhotos(true);
    } else {
      // Reached the end of all photos
      stopAutoplay();
      return;
    }
  }
  
  const photo = state.photos[state.modalPhotoIndex];
  if (!photo) {
    stopAutoplay();
    return;
  }
  
  const waitVideo = $('autoplay-wait-video').checked;
  const durationStr = $('autoplay-duration').value;
  const durationMs = (parseInt(durationStr) || 3) * 1000;
  
  let isVideoOrLive = photo.file_type === "MOV" || photo.is_live_photo;
  
  if (waitVideo && isVideoOrLive) {
    // We need to wait for the video to play
    // It takes a bit for the video element to be injected by modal.js
    setTimeout(() => {
      if (!isAutoplaying) return;
      const modalMedia = document.querySelectorAll('.modal-media');
      let videoEl = Array.from(modalMedia).find(el => el.tagName === "VIDEO");
      
      if (!videoEl && photo.is_live_photo) {
         // trigger live photo play badge
         const container = $('modal-image-container');
         if (container) {
            const divs = container.getElementsByTagName('div');
            for (let d of divs) {
               if (d.textContent === '▶ 播放' || d.textContent === 'PLAYING...') {
                  if (d.textContent === '▶ 播放') d.click();
                  break;
               }
            }
         }
         // Give it a moment to inject video
         setTimeout(() => {
            const newMedia = document.querySelectorAll('.modal-media, video');
            videoEl = Array.from(newMedia).find(el => el.tagName === "VIDEO");
            waitForVideo(videoEl, durationMs);
         }, 300);
      } else {
         waitForVideo(videoEl, durationMs);
      }
    }, 200);
  } else {
    // Standard delay
    autoplayTimer = setTimeout(nextSlide, durationMs);
  }
}

function waitForVideo(videoEl, fallbackMs) {
    if (videoEl) {
        // Ensure it is playing
        if (videoEl.paused) videoEl.play().catch(e => {});
        videoEl.onended = () => {
            if (isAutoplaying) setTimeout(nextSlide, 500); // 500ms pause after video
        };
        videoEl.onerror = () => {
            if (isAutoplaying) setTimeout(nextSlide, fallbackMs);
        }
    } else {
        autoplayTimer = setTimeout(nextSlide, fallbackMs);
    }
}

function nextSlide() {
  if (!isAutoplaying) return;
  if (state.modalPhotoIndex < state.photos.length - 1) {
    state.modalPhotoIndex++;
    renderModalContent();
    autoplayLoop();
  } else {
    // Need to load more, let loop handle it
    autoplayLoop();
  }
}

export function stopAutoplay() {
  isAutoplaying = false;
  if (autoplayTimer) clearTimeout(autoplayTimer);
  $('autoplay-controls').style.display = 'none';
}
