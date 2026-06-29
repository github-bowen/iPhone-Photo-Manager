import { state } from './state.js';
import { t } from './i18n.js';
import { $, formatDate, formatTime, formatFileSize, formatDuration } from './utils.js';

export function openModal(index) {
  state.modalPhotoIndex = index;
  const modalBackdrop = $("modal-backdrop");
  modalBackdrop.classList.add("active");
  document.body.style.overflow = "hidden";
  renderModalContent();
}

export function closeModal() {
  state.modalPhotoIndex = -1;
  const modalBackdrop = $("modal-backdrop");
  const modalImageContainer = $("modal-image-container");
  const modalInfo = $("modal-info");

  modalBackdrop.classList.remove("active");
  document.body.style.overflow = "";

  const existing = modalImageContainer.querySelectorAll("img, video");
  existing.forEach(function (el) {
    if (el.tagName === "VIDEO") el.pause();
    if (el.classList.contains("modal-media")) el.remove();
  });

  modalInfo.replaceChildren();
}

export function renderModalContent() {
  const photo = state.photos[state.modalPhotoIndex];
  if (!photo) return;

  const modalImageContainer = $("modal-image-container");
  const modalPrev = $("modal-prev");
  const modalNext = $("modal-next");

  const existingMedia = modalImageContainer.querySelectorAll(".modal-media");
  existingMedia.forEach(function (el) {
    if (el.tagName === "VIDEO") el.pause();
    el.remove();
  });

  if (photo.file_type === "MOV") {
    const video = document.createElement("video");
    video.className = "modal-media";
    video.controls = true;
    video.autoplay = true;
    video.src = "/api/photos/" + photo.id + "/file";
    modalImageContainer.insertBefore(video, modalPrev);
  } else {
    const wrapper = document.createElement("div");
    wrapper.className = "modal-media";
    wrapper.style.position = "relative";
    wrapper.style.display = "flex";
    wrapper.style.justifyContent = "center";
    wrapper.style.alignItems = "center";
    wrapper.style.width = "100%";
    wrapper.style.height = "100%";

    const img = document.createElement("img");
    img.style.maxWidth = "100%";
    img.style.maxHeight = "100%";
    img.style.objectFit = "contain";
    img.alt = photo.filename || t("photo_alt");
    img.src = state.loadOriginalOnClick 
              ? "/api/photos/" + photo.id + "/render" 
              : "/api/photos/" + photo.id + "/thumbnail/medium";
    wrapper.appendChild(img);

    if (photo.is_live_photo) {
      const liveBadge = document.createElement("div");
      liveBadge.textContent = "▶ 播放";
      liveBadge.style.position = "absolute";
      liveBadge.style.top = "20px";
      liveBadge.style.left = "20px";
      liveBadge.style.background = "rgba(255,255,255,0.8)";
      liveBadge.style.color = "#000";
      liveBadge.style.padding = "4px 8px";
      liveBadge.style.borderRadius = "4px";
      liveBadge.style.fontWeight = "bold";
      liveBadge.style.cursor = "pointer";
      liveBadge.style.boxShadow = "0 2px 4px rgba(0,0,0,0.2)";
      liveBadge.style.transition = "background 0.2s";
      
      let isPlaying = false;
      const playLive = () => {
          if (isPlaying) return;
          isPlaying = true;
          liveBadge.textContent = "PLAYING...";
          liveBadge.style.background = "rgba(255,255,255,1)";
          
          const video = document.createElement("video");
          video.style.position = "absolute";
          video.style.top = "0";
          video.style.left = "0";
          video.style.width = "100%";
          video.style.height = "100%";
          video.style.objectFit = "contain";
          video.autoplay = true;
          video.src = "/api/photos/" + photo.id + "/live-video";
          
          video.onended = () => {
              video.remove();
              img.style.visibility = "visible";
              liveBadge.textContent = "▶ 播放";
              liveBadge.style.background = "rgba(255,255,255,0.8)";
              isPlaying = false;
          };
          
          img.style.visibility = "hidden";
          wrapper.appendChild(video);
      };

      liveBadge.onclick = (e) => { e.stopPropagation(); playLive(); };
      wrapper.appendChild(liveBadge);
    }
    
    modalImageContainer.insertBefore(wrapper, modalPrev);
  }

  renderModalInfo(photo);

  modalPrev.style.display = state.modalPhotoIndex > 0 ? "" : "none";
  modalNext.style.display = state.modalPhotoIndex < state.photos.length - 1 ? "" : "none";
}

function renderModalInfo(photo) {
  const modalInfo = $("modal-info");
  const modalImageContainer = $("modal-image-container");
  modalInfo.replaceChildren();

  const title = document.createElement("div");
  title.className = "modal-info-title";
  title.textContent = photo.filename || "Untitled";
  modalInfo.appendChild(title);

  if (photo.display_location) {
    const loc = document.createElement("div");
    loc.className = "modal-info-location";
    loc.textContent = "📍 " + photo.display_location;
    modalInfo.appendChild(loc);
  }

  if (photo.taken_at) {
    const section = createInfoSection(t("date_time_sec"));
    addInfoRow(section, t("date_lbl"), formatDate(photo.taken_at));
    addInfoRow(section, t("time_lbl"), formatTime(photo.taken_at));
    if (photo.timezone) {
      addInfoRow(section, t("timezone_lbl"), photo.timezone);
    }
    modalInfo.appendChild(section);
  }

  if (photo.camera_make || photo.camera_model || photo.lens_model) {
    const section = createInfoSection(t("camera_sec"));
    if (photo.camera_make) addInfoRow(section, t("make_lbl"), photo.camera_make);
    if (photo.camera_model) addInfoRow(section, t("model_lbl"), photo.camera_model);
    if (photo.lens_model) addInfoRow(section, t("lens_lbl"), photo.lens_model);
    modalInfo.appendChild(section);
  }

  const fileSection = createInfoSection(t("file_sec"));
  addInfoRow(fileSection, t("type_lbl"), photo.file_type);
  addInfoRow(fileSection, t("size_lbl"), formatFileSize(photo.file_size));
  if (photo.width && photo.height) {
    addInfoRow(fileSection, t("dim_lbl"), photo.width + " × " + photo.height);
  }
  if (photo.duration) {
    addInfoRow(fileSection, t("dur_lbl"), formatDuration(photo.duration));
  }
  addInfoRow(fileSection, t("dir_lbl"), photo.directory);
  modalInfo.appendChild(fileSection);

  if (photo.latitude != null && photo.longitude != null) {
    const gpsSection = createInfoSection(t("gps_sec"));
    addInfoRow(gpsSection, t("lat_lbl"), photo.latitude.toFixed(6));
    addInfoRow(gpsSection, t("lng_lbl"), photo.longitude.toFixed(6));
    if (photo.altitude != null) {
      addInfoRow(gpsSection, t("alt_lbl"), photo.altitude.toFixed(1) + "m");
    }
    modalInfo.appendChild(gpsSection);
  }

  const tagsSection = createInfoSection(t("tags_sec"));
  if (photo.is_live_photo) addInfoRow(tagsSection, t("live_photo_lbl"), t("yes_lbl"));
  if (photo.is_screenshot) addInfoRow(tagsSection, t("screenshot_lbl"), t("yes_lbl"));
  if (photo.is_edited) addInfoRow(tagsSection, t("edited_lbl"), t("yes_lbl"));
  if (tagsSection.childElementCount > 1) {
    modalInfo.appendChild(tagsSection);
  }

  const actionsSection = createInfoSection(t("actions_sec"));
  const viewOriginalBtn = document.createElement("button");
  viewOriginalBtn.className = "filter-btn";
  viewOriginalBtn.style.width = "100%";
  viewOriginalBtn.style.marginTop = "8px";
  viewOriginalBtn.style.justifyContent = "center";
  viewOriginalBtn.style.background = "var(--accent-gradient)";
  viewOriginalBtn.style.color = "#fff";
  viewOriginalBtn.style.border = "none";
  viewOriginalBtn.textContent = t("view_original");
  viewOriginalBtn.onclick = function() {
      if (photo.file_type === "MOV") {
           window.open("/api/photos/" + photo.id + "/file", "_blank");
      } else {
           if (state.loadOriginalOnClick) {
               window.open("/api/photos/" + photo.id + "/file", "_blank");
               return;
           }
           viewOriginalBtn.textContent = t("loading") || "Loading...";
           viewOriginalBtn.disabled = true;
           viewOriginalBtn.style.opacity = "0.7";
           
           const imgElement = modalImageContainer.querySelector("img");
           if (imgElement) {
               const newImg = new Image();
               newImg.onload = () => {
                   imgElement.src = newImg.src;
                   viewOriginalBtn.textContent = t("view_original") + " (Loaded)";
               };
               newImg.onerror = () => {
                   viewOriginalBtn.textContent = "Error loading original";
                   viewOriginalBtn.disabled = false;
                   viewOriginalBtn.style.opacity = "1";
               };
               newImg.src = "/api/photos/" + photo.id + "/render";
           }
      }
  };
  actionsSection.appendChild(viewOriginalBtn);
  modalInfo.appendChild(actionsSection);
}

function createInfoSection(titleText) {
  const section = document.createElement("div");
  section.className = "modal-info-section";

  const title = document.createElement("div");
  title.className = "modal-info-section-title";
  title.textContent = titleText;
  section.appendChild(title);

  return section;
}

function addInfoRow(section, label, value) {
  const row = document.createElement("div");
  row.className = "modal-info-row";

  const labelEl = document.createElement("span");
  labelEl.className = "modal-info-label";
  labelEl.textContent = label;
  row.appendChild(labelEl);

  const valueEl = document.createElement("span");
  valueEl.className = "modal-info-value";
  valueEl.textContent = value || "—";
  row.appendChild(valueEl);

  section.appendChild(row);
}
