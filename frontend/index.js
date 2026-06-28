/**
 * iPhone Photo Manager — Frontend Logic
 *
 * Handles photo grid rendering, filtering, infinite scroll,
 * modal viewer with EXIF details, and Live Photo playback.
 *
 * Security: All DOM manipulation uses createElement/textContent (no innerHTML).
 */

(function () {
  "use strict";

  // --- State ---
  const state = {
    photos: [],
    currentPage: 1,
    totalPages: 0,
    total: 0,
    perPage: 60,
    loading: false,
    activeFilter: "all",
    activeLocation: null,
    dateFrom: null,
    dateTo: null,
    searchQuery: "",
    modalPhotoIndex: -1,
    scanComplete: false,
    timeline: [],
    locations: [],
    language: "zh",
    theme: "light",
    loadOriginalOnClick: false,
  };

  const i18n = {
    en: {
      app_title: "iPhone Photo Manager",
      timeline: "Timeline",
      locations: "Locations",
      load_original: "Load 4K Original",
      country_only: "Country Only",
      loading: "Loading...",
      scanning: "Scanning...",
      search_placeholder: "Search by location...",
      filter_all: "All",
      filter_photos: "Photos",
      filter_videos: "Videos",
      filter_screenshots: "Screenshots",
      date_from: "From date",
      date_to: "To date",
      load_more: "Load More",
      close_btn: "Close (Esc)",
      prev_btn: "Previous (←)",
      next_btn: "Next (→)",
      initializing: "Initializing...",
      failed_load: "Failed to load photos",
      try_again: "Please try again later.",
      no_photos: "No photos found",
      adjust_filters: "Try adjusting your filters.",
      unknown_date: "Unknown Date",
      photo_alt: "Photo",
      video_dur: "Video",
      date_time_sec: "Date & Time",
      date_lbl: "Date",
      time_lbl: "Time",
      timezone_lbl: "Timezone",
      camera_sec: "Camera",
      make_lbl: "Make",
      model_lbl: "Model",
      lens_lbl: "Lens",
      file_sec: "File",
      type_lbl: "Type",
      size_lbl: "Size",
      dim_lbl: "Dimensions",
      dur_lbl: "Duration",
      dir_lbl: "Directory",
      gps_sec: "GPS",
      lat_lbl: "Latitude",
      lng_lbl: "Longitude",
      alt_lbl: "Altitude",
      tags_sec: "Tags",
      live_photo_lbl: "Live Photo",
      screenshot_lbl: "Screenshot",
      edited_lbl: "Edited",
      yes_lbl: "Yes",
      all_photos: "All Photos",
      all_locations: "All Locations",
      stats_photos: "photos",
      stats_locations: "locations",
      scan_progress: "Scanning files...",
      country_only: "Country / City View",
      actions_sec: "Actions",
      view_original: "View Original File"
    },
    zh: {
      app_title: "iPhone 照片管理",
      timeline: "时间线",
      locations: "地点",
      load_original: "加载 4K 原图",
      country_only: "仅显示国家",
      loading: "加载中...",
      scanning: "正在扫描...",
      search_placeholder: "按地点搜索...",
      filter_all: "全部",
      filter_photos: "照片",
      filter_videos: "视频",
      filter_screenshots: "截图",
      date_from: "开始日期",
      date_to: "结束日期",
      load_more: "加载更多",
      close_btn: "关闭 (Esc)",
      prev_btn: "上一张 (←)",
      next_btn: "下一张 (→)",
      initializing: "初始化中...",
      failed_load: "加载照片失败",
      try_again: "请稍后再试。",
      no_photos: "未找到照片",
      adjust_filters: "尝试调整过滤条件。",
      unknown_date: "未知日期",
      photo_alt: "照片",
      video_dur: "视频",
      date_time_sec: "日期与时间",
      date_lbl: "日期",
      time_lbl: "时间",
      timezone_lbl: "时区",
      camera_sec: "相机",
      make_lbl: "品牌",
      model_lbl: "型号",
      lens_lbl: "镜头",
      file_sec: "文件",
      type_lbl: "类型",
      size_lbl: "大小",
      dim_lbl: "尺寸",
      dur_lbl: "时长",
      dir_lbl: "目录",
      gps_sec: "GPS",
      lat_lbl: "纬度",
      lng_lbl: "经度",
      alt_lbl: "海拔",
      tags_sec: "标签",
      live_photo_lbl: "实况照片",
      screenshot_lbl: "截图",
      edited_lbl: "已编辑",
      yes_lbl: "是",
      all_photos: "所有照片",
      all_locations: "所有地点",
      stats_photos: "张照片",
      stats_locations: "个地点",
      scan_progress: "正在扫描文件...",
      country_only: "按国家/城市层级显示",
      actions_sec: "操作",
      view_original: "查看原图 / 原始文件"
    }
  };

  function t(key) {
    return i18n[state.language][key] || key;
  }

  function applyTranslations() {
    document.querySelectorAll("[data-i18n]").forEach(el => {
      el.textContent = t(el.getAttribute("data-i18n"));
    });
    document.querySelectorAll("[data-i18n-placeholder]").forEach(el => {
      el.placeholder = t(el.getAttribute("data-i18n-placeholder"));
    });
    document.querySelectorAll("[data-i18n-title]").forEach(el => {
      el.title = t(el.getAttribute("data-i18n-title"));
    });
  }

  // --- DOM References ---
  const $ = (id) => document.getElementById(id);
  const gallery = $("gallery");
  const galleryContainer = $("gallery-container");
  const loadMoreContainer = $("load-more-container");
  const loadMoreBtn = $("load-more-btn");
  const modalBackdrop = $("modal-backdrop");
  const modalImageContainer = $("modal-image-container");
  const modalInfo = $("modal-info");
  const modalClose = $("modal-close");
  const modalPrev = $("modal-prev");
  const modalNext = $("modal-next");
  const searchInput = $("search-input");
  const sidebar = $("sidebar");
  const sidebarTimeline = $("sidebar-timeline");
  const sidebarLocations = $("sidebar-locations");
  const sidebarStats = $("sidebar-stats");
  const sidebarOverlay = $("sidebar-overlay");
  const mobileMenuBtn = $("mobile-menu-btn");
  const scanBanner = $("scan-banner");
  const scanBannerText = $("scan-banner-text");
  const scanBannerProgress = $("scan-banner-progress");
  const loadingOverlay = $("loading-overlay");
  const loadingText = $("loading-text");
  const loadingProgressBar = $("loading-progress-bar");
  const dateFromInput = $("date-from");
  const dateToInput = $("date-to");
  const loadOriginalToggle = $("load-original-toggle");
  const langToggle = $("lang-toggle");

  // --- API Helpers ---
  async function api(endpoint) {
    const res = await fetch(endpoint);
    if (!res.ok) {
      throw new Error("API error: " + res.status);
    }
    return res.json();
  }

  // --- Photo Loading ---
  async function loadPhotos(append) {
    if (state.loading) return;
    state.loading = true;

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

    if (state.activeLocation) {
      params.set("location", state.activeLocation);
    }
    if (state.activeCountry) {
      params.set("country", state.activeCountry);
    }
    if (state.activeCity) {
      params.set("city", state.activeCity);
    }
    if (state.dateFrom) {
      params.set("date_from", state.dateFrom + "T00:00:00");
    }
    if (state.dateTo) {
      params.set("date_to", state.dateTo + "T23:59:59");
    }
    if (state.language) {
      params.set("lang", state.language);
    }

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
      // Display generic error in gallery
      if (!append) {
        gallery.replaceChildren();
        const emptyEl = createEmptyState("⚠️", t("failed_load"), t("try_again"));
        gallery.appendChild(emptyEl);
      }
    }

    state.loading = false;
  }

  // --- Gallery Rendering ---
  function renderGallery(append) {
    if (!append) {
      gallery.replaceChildren();
    }

    if (state.photos.length === 0) {
      const emptyEl = createEmptyState("📷", t("no_photos"), t("adjust_filters"));
      gallery.appendChild(emptyEl);
      return;
    }

    // Group photos by date
    const groups = groupByDate(append ? getNewPhotos() : state.photos);

    for (const [date, photos] of Object.entries(groups)) {
      // Check if date group already exists (for append mode)
      let groupEl = append ? gallery.querySelector('[data-date="' + CSS.escape(date) + '"]') : null;
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

  function getNewPhotos() {
    // For append mode, return only photos from the last loaded page
    const start = (state.currentPage - 1) * state.perPage;
    return state.photos.slice(start);
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

  function createPhotoCard(photo) {
    const card = document.createElement("div");
    card.className = "photo-card";
    card.setAttribute("data-id", photo.id);

    // Thumbnail image
    const img = document.createElement("img");
    img.className = "loading";
    img.alt = photo.filename || "照片";
    img.loading = "lazy";
    img.src = "/api/photos/" + photo.id + "/thumbnail/small?v=" + Date.now();
    img.addEventListener("load", function () {
      img.className = "loaded";
    });
    img.addEventListener("error", function () {
      img.className = "loaded";
      // Show placeholder on error
      img.style.backgroundColor = "var(--bg-tertiary)";
    });
    card.appendChild(img);

    // Overlay with badges
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

    // Live Photo: preload video on hover
    if (photo.is_live_photo && photo.live_photo_mov) {
      card.addEventListener("mouseenter", function () {
        if (!card.querySelector("video")) {
          // Find the MOV photo's ID by searching in loaded photos
          const movPath = photo.live_photo_mov;
          const video = document.createElement("video");
          video.muted = true;
          video.loop = true;
          video.playsInline = true;
          video.src = "/api/photos/" + photo.id + "/file";
          // We use the HEIC file endpoint but need the MOV
          // Actually, serve the MOV file via a direct path
          // The live_photo_mov is a relative path, let's find the MOV by looking it up
          video.src = "/api/photos/" + photo.id + "/live-video";
          video.play().catch(function () {});
          card.appendChild(video);
        } else {
          const v = card.querySelector("video");
          if (v) v.play().catch(function () {});
        }
      });

      card.addEventListener("mouseleave", function () {
        const v = card.querySelector("video");
        if (v) {
          v.pause();
          v.currentTime = 0;
        }
      });
    }

    // Click to open modal
    card.addEventListener("click", function () {
      const idx = state.photos.findIndex(function (p) { return p.id === photo.id; });
      if (idx >= 0) {
        openModal(idx);
      }
    });

    return card;
  }

  function createEmptyState(icon, text, subtext) {
    const el = document.createElement("div");
    el.className = "empty-state";

    const iconEl = document.createElement("div");
    iconEl.className = "empty-state-icon";
    iconEl.textContent = icon;
    el.appendChild(iconEl);

    const textEl = document.createElement("div");
    textEl.className = "empty-state-text";
    textEl.textContent = text;
    el.appendChild(textEl);

    const subEl = document.createElement("div");
    subEl.className = "empty-state-sub";
    subEl.textContent = subtext;
    el.appendChild(subEl);

    return el;
  }

  // --- Modal ---
  function openModal(index) {
    state.modalPhotoIndex = index;
    modalBackdrop.classList.add("active");
    document.body.style.overflow = "hidden";
    renderModalContent();
  }

  function closeModal() {
    state.modalPhotoIndex = -1;
    modalBackdrop.classList.remove("active");
    document.body.style.overflow = "";

    // Clean up modal content
    const existing = modalImageContainer.querySelectorAll("img, video");
    existing.forEach(function (el) {
      if (el.tagName === "VIDEO") el.pause();
      if (el.classList.contains("modal-media")) el.remove();
    });

    modalInfo.replaceChildren();
  }

  function renderModalContent() {
    const photo = state.photos[state.modalPhotoIndex];
    if (!photo) return;

    // Clean up previous media
    const existingMedia = modalImageContainer.querySelectorAll(".modal-media");
    existingMedia.forEach(function (el) {
      if (el.tagName === "VIDEO") el.pause();
      el.remove();
    });

    // Show image or video
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

    // Render info panel
    renderModalInfo(photo);

    // Update nav button visibility
    modalPrev.style.display = state.modalPhotoIndex > 0 ? "" : "none";
    modalNext.style.display = state.modalPhotoIndex < state.photos.length - 1 ? "" : "none";
  }

  function renderModalInfo(photo) {
    modalInfo.replaceChildren();

    // Title
    const title = document.createElement("div");
    title.className = "modal-info-title";
    title.textContent = photo.filename || "Untitled";
    modalInfo.appendChild(title);

    // Location
    if (photo.display_location) {
      const loc = document.createElement("div");
      loc.className = "modal-info-location";
      loc.textContent = "📍 " + photo.display_location;
      modalInfo.appendChild(loc);
    }

    // Date & Time section
    if (photo.taken_at) {
      const section = createInfoSection(t("date_time_sec"));
      addInfoRow(section, t("date_lbl"), formatDate(photo.taken_at));
      addInfoRow(section, t("time_lbl"), formatTime(photo.taken_at));
      if (photo.timezone) {
        addInfoRow(section, t("timezone_lbl"), photo.timezone);
      }
      modalInfo.appendChild(section);
    }

    // Camera section
    if (photo.camera_make || photo.camera_model || photo.lens_model) {
      const section = createInfoSection(t("camera_sec"));
      if (photo.camera_make) addInfoRow(section, t("make_lbl"), photo.camera_make);
      if (photo.camera_model) addInfoRow(section, t("model_lbl"), photo.camera_model);
      if (photo.lens_model) addInfoRow(section, t("lens_lbl"), photo.lens_model);
      modalInfo.appendChild(section);
    }

    // File section
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

    // GPS section
    if (photo.latitude != null && photo.longitude != null) {
      const gpsSection = createInfoSection(t("gps_sec"));
      addInfoRow(gpsSection, t("lat_lbl"), photo.latitude.toFixed(6));
      addInfoRow(gpsSection, t("lng_lbl"), photo.longitude.toFixed(6));
      if (photo.altitude != null) {
        addInfoRow(gpsSection, t("alt_lbl"), photo.altitude.toFixed(1) + "m");
      }
      modalInfo.appendChild(gpsSection);
    }

    // Tags section
    const tagsSection = createInfoSection(t("tags_sec"));
    if (photo.is_live_photo) addInfoRow(tagsSection, t("live_photo_lbl"), t("yes_lbl"));
    if (photo.is_screenshot) addInfoRow(tagsSection, t("screenshot_lbl"), t("yes_lbl"));
    if (photo.is_edited) addInfoRow(tagsSection, t("edited_lbl"), t("yes_lbl"));
    if (tagsSection.childElementCount > 1) {
      modalInfo.appendChild(tagsSection);
    }

    // Actions section
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
             // Change the modal image source to the high-res render
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

  // --- Sidebar ---
  let sidebarTimer = null;

  function closeMobileSidebar() {
    if (sidebar && sidebarOverlay) {
      sidebar.classList.remove("open");
      sidebarOverlay.classList.remove("show");
      if (sidebarTimer) clearTimeout(sidebarTimer);
    }
  }

  function resetSidebarTimer() {
    if (sidebarTimer) clearTimeout(sidebarTimer);
    sidebarTimer = setTimeout(closeMobileSidebar, 5000);
  }

  async function loadTimeline() {
    try {
      const data = await api("/api/timeline");
      state.timeline = data;
      renderTimeline();
    } catch (e) {
      // Silently fail — timeline is non-critical
    }
  }

  function renderTimeline() {
    sidebarTimeline.replaceChildren();

    // Group by month
    const months = {};
    for (const item of state.timeline) {
      if (!item.date) continue;
      const month = item.date.substring(0, 7); // YYYY-MM
      if (!months[month]) {
        months[month] = { count: 0, days: [] };
      }
      months[month].count += item.count;
      months[month].days.push(item);
    }

    // "All" item
    const allItem = createSidebarItem(t("all_photos"), state.total, function () {
      state.dateFrom = null;
      state.dateTo = null;
      dateFromInput.value = "";
      dateToInput.value = "";
      resetAndReload();
      resetSidebarTimer();
      setActiveSidebarItem(sidebarTimeline, allItem);
    });
    if (!state.dateFrom && !state.dateTo) {
        allItem.classList.add("active");
    }
    sidebarTimeline.appendChild(allItem);

    for (const [month, data] of Object.entries(months)) {
      const wrapper = document.createElement("div");
      
      const isExpanded = state.expandedMonths && state.expandedMonths.has(month);
      const prefix = isExpanded ? "▼ " : "▶ ";
      
      const label = formatMonthLabel(month);
      const item = createSidebarItem(prefix + label, data.count, function () {
        if (!state.expandedMonths) state.expandedMonths = new Set();
        if (state.expandedMonths.has(month)) {
          state.expandedMonths.delete(month);
        } else {
          state.expandedMonths.add(month);
        }
        
        // Set date range to this month safely
        const parts = month.split("-");
        const y = parseInt(parts[0], 10);
        const m = parseInt(parts[1], 10);
        const lastDay = new Date(y, m, 0).getDate();
        
        state.dateFrom = `${month}-01`;
        state.dateTo = `${month}-${lastDay}`;
        dateFromInput.value = state.dateFrom;
        dateToInput.value = state.dateTo;
        resetAndReload();
        resetSidebarTimer();
        
        renderTimeline();
      });
      
      if (state.dateFrom === `${month}-01` && state.dateTo === `${month}-${new Date(parseInt(month.split("-")[0]), parseInt(month.split("-")[1]), 0).getDate()}`) {
          item.classList.add("active");
      }
      
      wrapper.appendChild(item);
      
      if (isExpanded) {
        const daysContainer = document.createElement("div");
        daysContainer.style.paddingLeft = "15px";
        
        for (const day of data.days) {
            const dayItem = createSidebarItem("  " + day.date, day.count, function(e) {
               e.stopPropagation();
               state.dateFrom = day.date;
               state.dateTo = day.date;
               dateFromInput.value = day.date;
               dateToInput.value = day.date;
               resetAndReload();
               resetSidebarTimer();
               renderTimeline();
            });
            if (state.dateFrom === day.date && state.dateTo === day.date) {
                dayItem.classList.add("active");
            }
            daysContainer.appendChild(dayItem);
        }
        wrapper.appendChild(daysContainer);
      }
      
      sidebarTimeline.appendChild(wrapper);
    }
  }

  async function loadLocations() {
    try {
      const data = await api(`/api/locations?lang=${state.language || "zh"}`);
      state.locations = data;
      renderLocations();
    } catch (e) {
      // Silently fail
    }
  }

  function renderLocations() {
    sidebarLocations.replaceChildren();

    // "All" item
    const allItem = createSidebarItem(t("all_locations"), "", function () {
      state.activeLocation = null;
      state.activeCity = null;
      state.activeCountry = null;
      searchInput.value = "";
      resetAndReload();
      setActiveSidebarItem(sidebarLocations, allItem);
    });
    if (!state.activeLocation && !state.activeCountry && !state.activeCity) {
      allItem.classList.add("active");
    }
    sidebarLocations.appendChild(allItem);

    const countries = {};
    for (const loc of state.locations) {
      if (!loc.location_name || !loc.display_location) continue;
      
      const partsEn = loc.location_name.split(", ");
      const countryEn = partsEn[partsEn.length - 1];
      
      const partsDisp = loc.display_location.split(", ");
      const countryDisp = partsDisp[partsDisp.length - 1];

      if (!countries[countryEn]) {
        countries[countryEn] = { display: countryDisp, count: 0, cities: [] };
      }
      countries[countryEn].count += loc.count;
      countries[countryEn].cities.push(loc);
    }
    
    const sortedCountries = Object.entries(countries).sort((a,b)=>b[1].count-a[1].count);
    for (const [countryEn, data] of sortedCountries) {
      const wrapper = document.createElement("div");
      
      const isExpanded = state.expandedCountries && state.expandedCountries.has(countryEn);
      const prefix = isExpanded ? "▼ " : "▶ ";
      
      const item = createSidebarItem(prefix + data.display, data.count, function (e) {
        if (!state.expandedCountries) state.expandedCountries = new Set();
        if (state.expandedCountries.has(countryEn)) {
          state.expandedCountries.delete(countryEn);
        } else {
          state.expandedCountries.add(countryEn);
        }
        
        state.activeLocation = null;
        state.activeCity = null;
        state.activeCountry = countryEn;
        searchInput.value = data.display;
        resetAndReload();
        resetSidebarTimer();
        
        renderLocations(); // re-render to show/hide cities
      });
      
      if (state.activeCountry === countryEn && !state.activeLocation && !state.activeCity) item.classList.add("active");
      wrapper.appendChild(item);
      
      if (isExpanded) {
        const citiesContainer = document.createElement("div");
        citiesContainer.style.paddingLeft = "15px";
        
        const groupedCities = {};
        function cleanCity(name) {
            if (!name) return name;
            let cleaned = name;
            if (cleaned.includes(" (")) cleaned = cleaned.split(" (")[0];
            if (cleaned.includes(" / ")) cleaned = cleaned.split(" / ")[0];
            return cleaned.trim();
        }

        for (const loc of data.cities) {
          const partsEn = loc.location_name.split(", ");
          const partsDisp = loc.display_location.split(", ");
          
          let cityEn = cleanCity(partsEn[0]);
          let cityDisp = cleanCity(partsDisp[0]);
          if (state.language === "zh" && (cityEn.toLowerCase() === "zuerich" || cityEn === "Zurich")) cityDisp = "苏黎世";
          else if (state.language === "en" && (cityDisp.toLowerCase() === "zuerich" || cityDisp === "苏黎世")) cityDisp = "Zurich";
          
          if (!groupedCities[cityEn]) {
              groupedCities[cityEn] = { display: cityDisp, count: 0 };
          }
          groupedCities[cityEn].count += loc.count;
        }
        
        const sortedCities = Object.entries(groupedCities).sort((a,b)=>b[1].count - a[1].count);
        for (const [cityKey, cityData] of sortedCities) {
          const cityItem = createSidebarItem("  " + cityData.display, cityData.count, function(e) {
             e.stopPropagation();
             state.activeLocation = null;
             state.activeCity = cityKey;
             state.activeCountry = countryEn;
             searchInput.value = cityData.display;
             resetAndReload();
             resetSidebarTimer();
             renderLocations();
          });
          if (state.activeCity === cityKey) cityItem.classList.add("active");
          citiesContainer.appendChild(cityItem);
        }
        wrapper.appendChild(citiesContainer);
      }
      sidebarLocations.appendChild(wrapper);
    }
  }

  function createSidebarItem(label, count, onClick) {
    const item = document.createElement("div");
    item.className = "sidebar-item";

    const labelEl = document.createElement("span");
    labelEl.textContent = label;
    item.appendChild(labelEl);

    if (count !== "" && count != null) {
      const countEl = document.createElement("span");
      countEl.className = "sidebar-item-count";
      countEl.textContent = count.toString();
      item.appendChild(countEl);
    }

    item.addEventListener("click", onClick);
    return item;
  }

  function setActiveSidebarItem(container, activeItem) {
    const items = container.querySelectorAll(".sidebar-item");
    items.forEach(function (it) { it.classList.remove("active"); });
    activeItem.classList.add("active");
  }

  // --- Scan Status Polling ---
  async function checkScanStatus() {
    try {
      const status = await api("/api/scan/status");

      if (status.status === "complete" || status.status === "idle") {
        scanBanner.classList.add("hidden");
        loadingOverlay.classList.add("hidden");

        if (!state.scanComplete) {
          state.scanComplete = true;
          // Reload everything
          state.currentPage = 1;
          await loadPhotos(false);
          await loadTimeline();
          await loadLocations();
          updateStats();
        }
        return;
      }

      // Show progress
      if (status.status === "scanning" || status.status === "generating_thumbnails" || status.status === "geocoding") {
        scanBanner.classList.remove("hidden");
        scanBannerText.textContent = status.message || status.status;

        let pct = 100;
        if (status.total > 0) {
          pct = Math.round((status.progress / status.total) * 100);
        }
        scanBannerProgress.style.width = pct + "%";

        // Also show on loading overlay if initial scan
        if (!state.scanComplete) {
          loadingOverlay.classList.remove("hidden");
          loadingText.textContent = status.message || status.status;
          loadingProgressBar.style.width = pct + "%";
        }

        // Poll again
        setTimeout(checkScanStatus, 2000);

        // Load partial results if scanning
        if (status.progress > 100 && state.photos.length === 0) {
          state.currentPage = 1;
          loadPhotos(false);
        }
      }
    } catch (e) {
      setTimeout(checkScanStatus, 5000);
    }
  }

  // --- Filter Handlers ---
  function setupFilters() {
    const filterBtns = document.querySelectorAll(".filter-btn");
    filterBtns.forEach(function (btn) {
      btn.addEventListener("click", function () {
        document.querySelectorAll(".filter-btn").forEach(b => b.classList.remove("active"));
        this.classList.add("active");
        const filter = this.dataset.filter;
        state.fileType = filter === "all" ? null : filter;
        resetAndReload();
        resetSidebarTimer();
      });
    });

    // Date filters
    dateFromInput.addEventListener("change", function () {
      state.dateFrom = this.value || null;
      resetAndReload();
    });

    dateToInput.addEventListener("change", function () {
      state.dateTo = this.value || null;
      resetAndReload();
    });

    // Search (location)
    let searchTimeout;
    searchInput.addEventListener("input", function () {
      clearTimeout(searchTimeout);
      searchTimeout = setTimeout(function () {
        const val = searchInput.value.trim();
        state.activeLocation = val || null;
        state.activeCountry = null;
        resetAndReload();
      }, 400);
    });

    // Event bindings for Sidebar

    // Mobile Sidebar Toggle
    if (mobileMenuBtn) {
      mobileMenuBtn.addEventListener("click", function () {
        sidebar.classList.add("open");
        sidebarOverlay.classList.add("show");
        resetSidebarTimer();
      });
    }
    if (sidebarOverlay) {
      sidebarOverlay.addEventListener("click", function () {
        closeMobileSidebar();
      });
    }

    // Load more
    loadMoreBtn.addEventListener("click", function () {
      state.currentPage++;
      loadPhotos(true);
    });
  }

  function resetAndReload() {
    state.currentPage = 1;
    state.photos = [];
    loadPhotos(false);
  }

  function updateLoadMoreButton() {
    if (state.currentPage < state.totalPages) {
      loadMoreContainer.style.display = "";
    } else {
      loadMoreContainer.style.display = "none";
    }
  }

  // --- Infinite Scroll ---
  function setupInfiniteScroll() {
    galleryContainer.addEventListener("scroll", function () {
      if (state.loading || state.currentPage >= state.totalPages) return;

      const scrollBottom = galleryContainer.scrollHeight - galleryContainer.scrollTop - galleryContainer.clientHeight;
      if (scrollBottom < 400) {
        state.currentPage++;
        loadPhotos(true);
      }
    });
  }

  // --- Keyboard Navigation ---
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

    modalClose.addEventListener("click", closeModal);
    modalPrev.addEventListener("click", function () {
      if (state.modalPhotoIndex > 0) {
        state.modalPhotoIndex--;
        renderModalContent();
      }
    });
    modalNext.addEventListener("click", function () {
      if (state.modalPhotoIndex < state.photos.length - 1) {
        state.modalPhotoIndex++;
        renderModalContent();
      }
    });
    modalBackdrop.addEventListener("click", function (e) {
      if (e.target === modalBackdrop || e.target === modalImageContainer) {
        closeModal();
      }
    });
  }

  // --- Helpers ---
  function updateStats() {
    sidebarStats.textContent = state.total + " " + t("stats_photos") + " · " +
      state.locations.length + " " + t("stats_locations");
  }

  function formatDateLabel(dateStr) {
    if (dateStr === "Unknown Date") return dateStr;
    try {
      const d = new Date(dateStr + "T12:00:00");
      return d.toLocaleDateString(state.language === "zh" ? "zh-CN" : "en-US", {
        year: "numeric", month: "long", day: "numeric", weekday: "long"
      });
    } catch (e) {
      return dateStr;
    }
  }

  function formatMonthLabel(monthStr) {
    try {
      const d = new Date(monthStr + "-01T12:00:00");
      return d.toLocaleDateString(state.language === "zh" ? "zh-CN" : "en-US", { year: "numeric", month: "long" });
    } catch (e) {
      return monthStr;
    }
  }

  function formatDate(isoStr) {
    if (!isoStr) return "—";
    try {
      const d = new Date(isoStr);
      return d.toLocaleDateString(state.language === "zh" ? "zh-CN" : "en-US", { year: "numeric", month: "long", day: "numeric" });
    } catch (e) {
      return isoStr;
    }
  }

  function formatTime(isoStr) {
    if (!isoStr) return "—";
    try {
      const d = new Date(isoStr);
      return d.toLocaleTimeString(state.language === "zh" ? "zh-CN" : "en-US", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
    } catch (e) {
      return isoStr;
    }
  }

  function formatFileSize(bytes) {
    if (!bytes) return "—";
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
    return (bytes / (1024 * 1024)).toFixed(1) + " MB";
  }

  function formatDuration(seconds) {
    if (!seconds) return "—";
    const m = Math.floor(seconds / 60);
    const s = Math.round(seconds % 60);
    if (m > 0) return m + ":" + s.toString().padStart(2, "0");
    return s + "s";
  }

  // --- Init ---
  async function init() {
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

      if (config.theme) state.theme = config.theme;

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

    // Check scan status first
    await checkScanStatus();

    // If scan is already done, load immediately
    if (state.scanComplete && state.photos.length === 0) {
      await loadPhotos(false);
      await loadTimeline();
      await loadLocations();
      updateStats();
    }
  }

  // Start when DOM is ready
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
