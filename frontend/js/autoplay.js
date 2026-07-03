import { state } from './state.js';
import { $ } from './utils.js';
import { resetAndReload, loadPhotos } from './gallery.js';
import { openModal, closeModal, renderModalContent } from './modal.js';

let autoplayTimer = null;
export let isAutoplaying = false;

export function initAutoplay() {
  const btn = $('autoplay-btn');
  const modal = $('autoplay-config-modal');
  const cancelBtn = $('autoplay-cancel-btn');
  const startBtn = $('autoplay-start-btn');
  const toggleBtn = $('modal-autoplay-toggle');
  const durationSlider = $('modal-autoplay-duration');

  // Move modal to document.body so it's not affected by any ancestor's
  // backdrop-filter / stacking-context that could clip position:fixed children
  if (modal && modal.parentElement !== document.body) {
    document.body.appendChild(modal);
  }

  if (btn) {
    btn.addEventListener('click', function(event) {
      console.log('Autoplay button clicked');
      openAutoplayConfig(event);
    });
  }
  
  if (cancelBtn) {
    cancelBtn.addEventListener('click', () => {
      modal.classList.remove('active');
    });
  }
  
  if (startBtn) {
    startBtn.addEventListener('click', startAutoplay);
  }

  if (toggleBtn) {
    toggleBtn.addEventListener('click', () => {
      if (isAutoplaying) stopAutoplay();
      else startAutoplayFromCurrent();
    });
  }

  if (durationSlider) {
    const durVal = $('modal-autoplay-dur-val');
    durationSlider.addEventListener('input', () => {
      if (durVal) durVal.textContent = durationSlider.value + "s";
    });
  }
}

function openAutoplayConfig() {
  const modal = $('autoplay-config-modal');
  console.log('openAutoplayConfig called, modal element:', modal);
  if (!modal) {
    console.error('Modal element not found');
    return;
  }
  console.log('Modal current display:', modal.style.display);
  
  // Pre-fill dates
  $('autoplay-date-from').value = state.dateFrom || "";
  $('autoplay-date-to').value = state.dateTo || "";

  // Pre-fill locations by country
  const locContainer = $('autoplay-location-container');
  if (locContainer) {
    locContainer.innerHTML = '';
    
    // Aggregate locations by country
    const countries = {};
    for (const loc of state.locations) {
      const parts = loc.display_location ? loc.display_location.split(', ') : [];
      const country = loc.display_country || (parts.length > 0 ? parts[parts.length - 1] : "Unknown");
      if (!countries[country]) countries[country] = 0;
      countries[country] += loc.count;
    }
    
    // Convert to array and sort by count descending
    const countryArray = Object.entries(countries)
      .map(([name, count]) => ({name, count}))
      .sort((a,b) => b.count - a.count);
    
    // Check which countries are currently active
    const activeCountries = state.activeCountry ? state.activeCountry.split(',') : [];
    
    for (const c of countryArray) {
      const label = document.createElement('label');
      label.className = 'autoplay-checkbox-label';
      const cb = document.createElement('input');
      cb.type = 'checkbox';
      cb.className = 'autoplay-country-cb';
      cb.value = c.name;
      // If we had active filters, check them; otherwise don't check any (or check all by default?)
      // Let's leave them unchecked by default, or checked if they match activeCountry
      if (activeCountries.includes(c.name)) {
        cb.checked = true;
      }
      label.appendChild(cb);
      label.appendChild(document.createTextNode(` ${c.name} (${c.count})`));
      locContainer.appendChild(label);
    }
  }

  // Pre-fill type based on current active filter
  const isAll = state.activeFilter === "all";
  $('autoplay-type-photo').checked = isAll || state.activeFilter.includes("HEIC");
  $('autoplay-type-video').checked = isAll || state.activeFilter.includes("MOV");
  $('autoplay-type-screenshot').checked = isAll || state.activeFilter.includes("PNG") || state.activeFilter === "PNG";

  // Hook up duration slider display
  const durSlider = $('autoplay-duration');
  const durDisplay = $('autoplay-duration-display');
  if (durSlider && durDisplay) {
    durSlider.oninput = () => { durDisplay.textContent = durSlider.value + 's'; };
  }

  modal.classList.add('active');

}

async function startAutoplay() {
  $('autoplay-config-modal').classList.remove('active');
  
  // Update state filters
  const dateFrom = $('autoplay-date-from').value;
  const dateTo = $('autoplay-date-to').value;
  state.dateFrom = dateFrom ? dateFrom : null;
  state.dateTo = dateTo ? dateTo : null;
  
  const countryCheckboxes = document.querySelectorAll('.autoplay-country-cb:checked');
  const countries = Array.from(countryCheckboxes).map(cb => cb.value);
  state.activeCountry = countries.length > 0 ? countries.join(',') : null;
  state.activeLocation = null; // Clear exact location filter to avoid conflicts
  
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
  
  // Read from modal specific controls if they exist, otherwise fallback to main config
  const waitVideoModal = $('modal-autoplay-wait-video');
  const durationModal = $('modal-autoplay-duration');
  
  const waitVideo = waitVideoModal ? waitVideoModal.checked : $('autoplay-wait-video').checked;
  const durationStr = durationModal ? durationModal.value : $('autoplay-duration').value;
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
  const toggleBtn = $('modal-autoplay-toggle');
  if (toggleBtn) toggleBtn.textContent = '▶';
}

export function startAutoplayFromCurrent() {
  isAutoplaying = true;
  const toggleBtn = $('modal-autoplay-toggle');
  if (toggleBtn) toggleBtn.textContent = '⏸';
  autoplayLoop();
}
