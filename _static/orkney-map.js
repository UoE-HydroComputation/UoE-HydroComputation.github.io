(() => {
  const mapElement = document.getElementById("orkney-map");
  if (!mapElement || !window.L) return;

  const map = L.map(mapElement, {minZoom: 7, maxZoom: 14});

  const bounds = L.latLngBounds([
    [57.53590702919824, -5.419641261511917],
    [59.89652974557744, -2.001352278191076],
  ]);
  map.createPane("tidal-sites");
  map.getPane("tidal-sites").style.zIndex = 650;
  map.createPane("observation-sites");
  map.getPane("observation-sites").style.zIndex = 660;
  const arrowBakedLayers = new Set(["mean-flood-speed", "mean-ebb-speed", "residual-current-speed"]);
  const tileVersion = (name) => arrowBakedLayers.has(name) ? "?v=arrows-baked-3" : "";
  const tilePath = (name) => `${new URL(`_static/case-study/${name}/`, document.baseURI).href}{z}/{x}/{y}.webp${tileVersion(name)}`;
  const detailTilePath = (region, name) => `${new URL(`_static/case-study/detail/${region}/${name}/`, document.baseURI).href}{z}/{x}/{y}.webp${tileVersion(name)}`;
  const detailRegions = [
    ["pentland-firth", L.latLngBounds([[58.59493068860289, -3.3440832169660424], [58.80183957036993, -2.826935799237717]])],
    ["westray-stronsay", L.latLngBounds([[58.95462946055599, -2.9999999999999916], [59.26820803541874, -2.5614390077878095]])],
  ];
  const sequential = ["#ffffff", "#c7e9f1", "#78c6d0", "#3196b2", "#176493", "#08306b"];
  const diverging = ["#762a83", "#c2a5cf", "#f7f7f7", "#a6dba0", "#1b7837"];
  const powerDensity = ["#fff7bc", "#fdae61", "#a50026"];
  const bathymetry = ["#d9f0f0", "#91c9d0", "#4a9fb8", "#276a9f", "#174375", "#081d58"];
  const definitions = [
    ["bathymetry", "Interpolated bathymetry", "0", "200 m", bathymetry, "Seafloor depth below mean water level.", "Bathymetry"],
    ["mean-speed", "Mean speed", "0", "2.5 m/s", sequential, "Mean of the instantaneous current-speed magnitude over the 14.765-day half spring–neap window.", "Half spring–neap cycle averages (14.765 days)"],
    ["mean-flood-speed", "Mean flood speed and direction", "0", "3 m/s", sequential, "Mean instantaneous current-speed magnitude during periods classified as flood from flow direction in the Inner Sound; arrows show the direction of the mean velocity vector. Arrows are omitted below 0.1 m/s.", "Half spring–neap cycle averages (14.765 days)"],
    ["mean-ebb-speed", "Mean ebb speed and direction", "0", "2.5 m/s", sequential, "Mean instantaneous current-speed magnitude during periods classified as ebb from flow direction in the Inner Sound; arrows show the direction of the mean velocity vector. Arrows are omitted below 0.1 m/s.", "Half spring–neap cycle averages (14.765 days)"],
    ["mean-power-density", "Mean kinetic power density", "0", "15,000 W/m²", powerDensity, "Mean of instantaneous 0.5 × 1025 × speed³ over the 14.765-day window; calculated from instantaneous speed, not Mean speed.", "Half spring–neap cycle averages (14.765 days)"],
    ["mean-flood-power-density", "Mean flood kinetic power density", "0", "15,000 W/m²", powerDensity, "Mean of instantaneous 0.5 × 1025 × speed³ during periods classified as flood from flow direction in the Inner Sound; the classification is applied across the model domain over the 14.765-day window.", "Half spring–neap cycle averages (14.765 days)"],
    ["mean-ebb-power-density", "Mean ebb kinetic power density", "0", "15,000 W/m²", powerDensity, "Mean of instantaneous 0.5 × 1025 × speed³ during periods classified as ebb from flow direction in the Inner Sound; the classification is applied across the model domain over the 14.765-day window.", "Half spring–neap cycle averages (14.765 days)"],
    ["residual-current-speed", "Residual current speed and direction", "0", "1.25 m/s", sequential, "Magnitude of the mean velocity over the 14.765-day window; arrows show its direction and are omitted below 0.1 m/s.", "Half spring–neap cycle averages (14.765 days)"],
    ["flood-ebb-asymmetry", "Normalized flood–ebb asymmetry", "−1", "1", diverging, "Mean flood speed minus mean ebb speed divided by their sum over the 14.765-day window. Zero indicates equal speeds; positive values indicate flood domination and negative values ebb domination. Flood and ebb periods are classified from flow direction in the Inner Sound and applied across the model domain. Undefined where both mean speeds are zero.", "Half spring–neap cycle averages (14.765 days)"],
    ["spring-mean-speed", "Daily spring tide mean speed", "0", "4 m/s", sequential, "Mean current-speed magnitude in the spring tidal-day window.", "Spring tide"],
    ["spring-mean-flood-speed", "Daily spring tide mean flood speed", "0", "4 m/s", sequential, "Mean flood speed in the spring tidal-day window.", "Spring tide"],
    ["spring-mean-ebb-speed", "Daily spring tide mean ebb speed", "0", "4 m/s", sequential, "Mean ebb speed in the spring tidal-day window.", "Spring tide"],
    ["spring-peak-flood-speed", "Peak spring flood speed", "0", "6 m/s", sequential, "Instantaneous speed at each node at the common timestamp within the 24.84-hour spring window when speed at the Inner Sound reference location was highest among times classified as flood. Flood is classified from flow direction there.", "Spring tide"],
    ["spring-peak-ebb-speed", "Peak spring ebb speed", "0", "6 m/s", sequential, "Instantaneous speed at each node at the common timestamp within the 24.84-hour spring window when speed at the Inner Sound reference location was highest among times classified as ebb. Ebb is classified from flow direction there.", "Spring tide"],
    ["neap-mean-speed", "Daily neap tide mean speed", "0", "3 m/s", sequential, "Mean current-speed magnitude in the neap tidal-day window.", "Neap tide"],
    ["neap-mean-flood-speed", "Daily neap tide mean flood speed", "0", "3 m/s", sequential, "Mean flood speed in the neap tidal-day window.", "Neap tide"],
    ["neap-mean-ebb-speed", "Daily neap tide mean ebb speed", "0", "3 m/s", sequential, "Mean ebb speed in the neap tidal-day window.", "Neap tide"],
    ["neap-peak-flood-speed", "Peak neap flood speed", "0", "5 m/s", sequential, "Instantaneous speed at each node at the common timestamp within the 24.84-hour neap window when speed at the Inner Sound reference location was highest among times classified as flood. Flood is classified from flow direction there.", "Neap tide"],
    ["neap-peak-ebb-speed", "Peak neap ebb speed", "0", "5 m/s", sequential, "Instantaneous speed at each node at the common timestamp within the 24.84-hour neap window when speed at the Inner Sound reference location was highest among times classified as ebb. Ebb is classified from flow direction there.", "Neap tide"],
    ["peak-flood-vorticity", "Peak flood vorticity", "< −0.05 s⁻¹", "> 0.05 s⁻¹", diverging, "At each node, the signed vertical vorticity value with the greatest absolute magnitude among flood-classified timesteps in the selected period; different nodes may represent different times. Values outside ±0.05 s⁻¹ are saturated at the colour-scale ends.", "Peak-flow diagnostics"],
    ["peak-ebb-vorticity", "Peak ebb vorticity", "< −0.05 s⁻¹", "> 0.05 s⁻¹", diverging, "At each node, the signed vertical vorticity value with the greatest absolute magnitude among ebb-classified timesteps in the selected period; different nodes may represent different times. Values outside ±0.05 s⁻¹ are saturated at the colour-scale ends.", "Peak-flow diagnostics"],
  ];
  const layers = Object.fromEntries(definitions.map(([id, label]) => [
    label,
    L.layerGroup([
      L.tileLayer(tilePath(id), {
        bounds,
        minZoom: 7,
        maxNativeZoom: 11,
        maxZoom: 14,
        noWrap: true,
        opacity: id === "bathymetry" ? 0.82 : 0.7,
      }),
      ...detailRegions.map(([region, detailBounds]) => L.tileLayer(detailTilePath(region, id), {
        bounds: detailBounds,
        minZoom: 12,
        maxNativeZoom: 13,
        maxZoom: 14,
        noWrap: true,
        opacity: 1,
      })),
    ]),
  ]));

  layers["Interpolated bathymetry"].addTo(map);
  const layerMenu = L.control({position: "topright"});
  layerMenu.onAdd = () => {
    const container = L.DomUtil.create("div", "leaflet-bar case-study-layer-menu");
    const details = document.createElement("details");
    details.open = true;
    const summary = document.createElement("summary");
    summary.textContent = "Layers";
    const modelSection = document.createElement("details");
    modelSection.className = "case-study-layer-menu__section";
    const modelSummary = document.createElement("summary");
    modelSummary.textContent = "Model output layers";
    const modelInfo = document.createElement("p");
    modelInfo.className = "case-study-layer-menu__model-info";
    modelInfo.append("Depth-averaged Thetis model output for 2–16 November 2022 (UTC), subject to adjoint-based calibration using many of the available ADCPs shown. The methodology reference can be found at ");
    const reference = document.createElement("a");
    reference.href = "https://agupubs.onlinelibrary.wiley.com/doi/full/10.1029/2025MS005399";
    reference.target = "_blank";
    reference.rel = "noopener noreferrer";
    reference.textContent = "this link";
    modelInfo.append(reference, ".");
    const list = document.createElement("div");
    list.className = "case-study-layer-menu__list";
    const categories = new Map();
    definitions.forEach((definition) => {
      const category = definition[6];
      if (!categories.has(category)) {
        const group = document.createElement("details");
        group.className = "case-study-layer-menu__group";
        const groupSummary = document.createElement("summary");
        groupSummary.textContent = category;
        const groupList = document.createElement("div");
        groupList.className = "case-study-layer-menu__group-list";
        group.append(groupSummary, groupList);
        categories.set(category, groupList);
        list.append(group);
      }
      const [, label, , , , description] = definition;
      const layer = layers[label];
      const option = document.createElement("label");
      const input = document.createElement("input");
      input.type = "checkbox";
      input.checked = map.hasLayer(layer);
      input.addEventListener("change", () => {
        if (input.checked) {
          layer.addTo(map);
          updateColourbar(label);
        } else {
          map.removeLayer(layer);
        }
      });
      map.on("overlayadd", ({layer: addedLayer}) => {
        if (addedLayer === layer) input.checked = true;
      });
      map.on("overlayremove", ({layer: removedLayer}) => {
        if (removedLayer === layer) input.checked = false;
      });
      const labelText = document.createElement("span");
      labelText.textContent = label;
      const info = document.createElement("button");
      info.type = "button";
      info.className = "case-study-layer-menu__info";
      info.textContent = "i";
      info.setAttribute("aria-label", `About ${label}`);
      const descriptionElement = document.createElement("span");
      descriptionElement.className = "case-study-layer-menu__description";
      descriptionElement.hidden = true;
      descriptionElement.textContent = description;
      info.setAttribute("aria-expanded", "false");
      info.addEventListener("click", (event) => {
        event.preventDefault();
        event.stopPropagation();
        descriptionElement.hidden = !descriptionElement.hidden;
        info.setAttribute("aria-expanded", String(!descriptionElement.hidden));
      });
      option.append(input, labelText, info, descriptionElement);
      categories.get(category).append(option);
    });
    modelSection.append(modelSummary, modelInfo, list);
    details.append(summary, modelSection, createTidalSitesSection(), createObservationsSection());
    container.append(details);
    L.DomEvent.disableClickPropagation(container);
    L.DomEvent.disableScrollPropagation(container);
    return container;
  };

  let siteLayer;
  const sitePages = {
    "Deer Sound": "sites/deer-sound.html",
    "EMEC Shapinsay Sound": "sites/emec-shapinsay-sound.html",
    "EMEC Fall of Warness": "sites/emec-fall-of-warness.html",
    "Fall of Warness": "sites/emec-fall-of-warness.html",
    "Westray South": "sites/westray-south.html",
    "Inner Sound": "sites/meygen-inner-sound.html",
    "Ness of Duncansby": "sites/ness-of-duncansby.html",
    "EMEC Stronsay Firth": "sites/emec-stronsay-firth.html",
    "Lashy Sound": "sites/lashy-sound.html",
    "Brough Ness": "sites/brough-ness.html",
    "Brims Tidal Array": "sites/brims-tidal-array.html",
  };
  const createTidalSitesSection = () => {
    const details = document.createElement("details");
    details.className = "case-study-layer-menu__section";
    const summary = document.createElement("summary");
    summary.textContent = "Tidal sites";
    const list = document.createElement("div");
    list.className = "case-study-layer-menu__list";
    const option = document.createElement("label");
    const input = document.createElement("input");
    input.type = "checkbox";
    input.checked = siteLayer ? map.hasLayer(siteLayer) : false;
    input.disabled = !siteLayer;
    input.addEventListener("change", () => {
      if (!siteLayer) return;
      if (input.checked) siteLayer.addTo(map);
      else map.removeLayer(siteLayer);
    });
    const label = document.createElement("span");
    label.textContent = "Crown Estate Scotland tidal sites";
    option.append(input, label);
    list.append(option);
    details.append(summary, list);

    map.on("overlayadd", ({layer}) => {
      if (layer === siteLayer) input.checked = true;
    });
    map.on("overlayremove", ({layer}) => {
      if (layer === siteLayer) input.checked = false;
    });
    return details;
  };

  const observationSites = window.ORKNEY_OBSERVATION_SITES;
  const observationLayers = {};
  const createObservationsSection = () => {
    const details = document.createElement("details");
    details.className = "case-study-layer-menu__section";
    const summary = document.createElement("summary");
    summary.textContent = "Observational data";
    const list = document.createElement("div");
    list.className = "case-study-layer-menu__list";
    const addOption = (parent, label, layerName) => {
      const option = document.createElement("label");
      const input = document.createElement("input");
      input.type = "checkbox";
      const layer = observationLayers[layerName];
      input.checked = layer ? map.hasLayer(layer) : false;
      input.disabled = !layer;
      input.addEventListener("change", () => {
        if (input.checked) layer.addTo(map);
        else map.removeLayer(layer);
      });
      map.on("overlayadd", ({layer}) => {
        if (layer === observationLayers[layerName]) input.checked = true;
      });
      map.on("overlayremove", ({layer}) => {
        if (layer === observationLayers[layerName]) input.checked = false;
      });
      const labelText = document.createElement("span");
      labelText.textContent = label;
      option.append(input, labelText);
      parent.append(option);
    };
    const adcpSection = document.createElement("details");
    adcpSection.className = "case-study-layer-menu__group";
    const adcpSummary = document.createElement("summary");
    adcpSummary.textContent = "ADCPs";
    const adcpList = document.createElement("div");
    adcpList.className = "case-study-layer-menu__group-list";
    addOption(adcpList, "Available", "ADCPs — available");
    addOption(adcpList, "Unavailable", "ADCPs — unavailable");
    adcpSection.append(adcpSummary, adcpList);
    list.append(adcpSection);
    const tideGaugeSection = document.createElement("details");
    tideGaugeSection.className = "case-study-layer-menu__group";
    const tideGaugeSummary = document.createElement("summary");
    tideGaugeSummary.textContent = "Tide gauges";
    const tideGaugeList = document.createElement("div");
    tideGaugeList.className = "case-study-layer-menu__group-list";
    addOption(tideGaugeList, "Tide gauges", "Tide gauges");
    tideGaugeSection.append(tideGaugeSummary, tideGaugeList);
    list.append(tideGaugeSection);
    details.append(summary, list);
    return details;
  };

  if (!observationSites) {
    console.error("Observation-site data asset is unavailable.");
  } else {
    const createObservationPopup = (site) => {
      const popup = document.createElement("dl");
      popup.className = "tidal-site-popup";
      const fields = [
        ["Name", site.properties.Name],
        ["Instrument type", site.properties.Type],
        ["Source", {
          MDE: "Marine Data Exchange (MDE)",
          "SDN-CDI": "SeaDataNet Common Data Index (SDN-CDI)",
          PSMSL: "Permanent Service for Mean Sea Level (PSMSL)",
          NOC: "National Oceanography Centre (NOC)",
          NTSLF: "National Tidal and Sea Level Facility (NTSLF)",
        }[site.properties.Source] || site.properties.Source],
        ["Availability", {0: "Unavailable", 1: "Available"}[site.properties.Indicator]],
        ["Latitude", site.latitude.toFixed(6)],
        ["Longitude", site.longitude.toFixed(6)],
        ["Easting", site.easting],
        ["Northing", site.northing],
      ];
      fields.forEach(([term, value]) => {
        if (value == null || value === "") return;
        const title = document.createElement("dt");
        title.textContent = term;
        const description = document.createElement("dd");
        description.textContent = value;
        popup.append(title, description);
      });
      return popup;
    };
    const observationTypes = {
      "ADCPs — available": {
        indicator: "1",
        color: "#1261a0",
        fillColor: "#4c9fcb",
      },
      "ADCPs — unavailable": {
        indicator: "0",
        color: "#66727d",
        fillColor: "#a8b0b6",
      },
      "Tide gauges": {
        indicator: "2",
        color: "#7a3d00",
        fillColor: "#e39a3b",
      },
    };
    Object.entries(observationTypes).forEach(([name, {indicator, color, fillColor}]) => {
      const layer = L.layerGroup(
        observationSites
          .filter((site) => site.properties.Indicator === indicator)
          .map((site) => L.circleMarker([site.latitude, site.longitude], {
            pane: "observation-sites",
            radius: 5,
            color,
            weight: 2,
            fillColor,
            fillOpacity: 0.9,
          }).bindPopup(createObservationPopup(site), {minWidth: 260, maxWidth: 400}))
      );
      observationLayers[name] = layer;
    });
  }

  const colourbar = L.control({position: "bottomleft"});
  colourbar.onAdd = () => {
    const element = L.DomUtil.create("div", "case-study-colourbar");
    L.DomEvent.disableClickPropagation(element);
    return element;
  };
  colourbar.addTo(map);
  const colourbarElement = document.querySelector(".case-study-colourbar");
  const updateColourbar = (label) => {
    const [, title, minimum, maximum, colours, note] = definitions.find(([, name]) => name === label);
    colourbarElement.replaceChildren();
    const heading = document.createElement("strong");
    heading.textContent = title;
    const gradient = document.createElement("div");
    gradient.className = "case-study-colourbar__gradient";
    gradient.style.background = `linear-gradient(to right, ${colours.join(", ")})`;
    const limits = document.createElement("div");
    limits.className = "case-study-colourbar__limits";
    const lowerLimit = document.createElement("span");
    lowerLimit.textContent = minimum;
    const upperLimit = document.createElement("span");
    upperLimit.textContent = maximum;
    limits.append(lowerLimit, upperLimit);
    colourbarElement.append(heading, gradient, limits);
    if (note) {
      const scaleNote = document.createElement("small");
      scaleNote.textContent = note;
      colourbarElement.append(scaleNote);
    }
  };
  updateColourbar("Interpolated bathymetry");
  map.on("overlayadd", ({name}) => {
    if (definitions.some(([, label]) => label === name)) updateColourbar(name);
  });

  const sites = window.ORKNEY_TIDAL_SITES;
  if (!sites) {
    console.error("Tidal-site data asset is unavailable.");
  } else {
      const createPopup = (properties) => {
        const popup = document.createElement("dl");
        popup.className = "tidal-site-popup";
        [
            ["Site", properties.Name_Prop],
            ["Tenant", properties.Name_Ten],
            ["Lease", properties.Lease_Stat],
            ["Project phase", properties.Inf_Status],
            ["Area", properties.area_km_2 == null ? null : `${properties.area_km_2} km²`],
        ].forEach(([term, value]) => {
          if (value == null || value === "") return;
          const title = document.createElement("dt");
          title.textContent = term;
          const description = document.createElement("dd");
          description.textContent = value;
          popup.append(title, description);
        });
        const page = sitePages[properties.Name_Prop];
        if (page) {
          const title = document.createElement("dt");
          title.textContent = "Details";
          const description = document.createElement("dd");
          const link = document.createElement("a");
          link.className = "tidal-site-popup__link";
          link.href = new URL(page, document.baseURI).href;
          link.textContent = "View site page";
          description.append(link);
          popup.append(title, description);
        }
        return popup;
      };
      const sitePolygons = L.geoJSON(sites, {
        pane: "tidal-sites",
        style: {color: "#8f2d00", weight: 4, fillColor: "#f7b267", fillOpacity: 0.72},
        onEachFeature: (feature, layer) => {
          layer.bindPopup(createPopup(feature.properties), {minWidth: 360, maxWidth: 440});
        },
      });
      siteLayer = sitePolygons;
      siteLayer.addTo(map);
      sitePolygons.bringToFront();
  }

  layerMenu.addTo(map);
  map.fitBounds(bounds, {padding: [18, 18]});
})();
