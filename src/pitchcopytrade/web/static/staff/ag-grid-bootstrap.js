(function () {
  if (!window.agGrid) {
    window.PCTAgGrid = {
      available: false,
      createGrid: function () {
        throw new Error("AG Grid Community is not loaded");
      }
    };
    return;
  }

  function textFromHtml(html) {
    var probe = document.createElement("div");
    probe.innerHTML = html || "";
    return (probe.textContent || probe.innerText || "").replace(/\s+/g, " ").trim();
  }

  function ensureThemeClass(container) {
    if (!container) {
      return;
    }
    container.classList.add("ag-theme-quartz", "pct-ag-theme");
  }

  function htmlCellRenderer(params) {
    var wrapper = document.createElement("div");
    wrapper.className = "pct-ag-cell-html";
    wrapper.innerHTML = params.value || "";
    return wrapper;
  }

  function createGrid(container, options) {
    ensureThemeClass(container);
    return agGrid.createGrid(container, options || {});
  }

  function resolveDomLayout() {
    if (window.matchMedia && window.matchMedia("(max-width: 768px)").matches) {
      return "autoHeight";
    }
    return "normal";
  }

  function tableToGrid(table) {
    if (!table || table.dataset.agGridMounted === "true") {
      return null;
    }

    var headers = Array.prototype.slice.call(table.querySelectorAll("thead th"));
    var skipRows = Array.prototype.slice.call(table.querySelectorAll("tbody tr[data-ag-grid-skip='true']"));
    var bodyRows = Array.prototype.slice.call(table.querySelectorAll("tbody tr")).filter(function (row) {
      return row.dataset.agGridSkip !== "true";
    });

    var columnDefs = headers.map(function (headerCell, index) {
      var headerName = textFromHtml(headerCell.innerHTML) || ("Колонка " + (index + 1));
      var field = "col_" + index;
      var quickField = "__text_" + index;
      var isActionColumn = headerName === "Действия" || headerName === "Открыть";
      return {
        headerName: headerName,
        field: field,
        sortable: !isActionColumn,
        filter: !isActionColumn,
        resizable: true,
        suppressMovable: true,
        wrapText: true,
        autoHeight: true,
        minWidth: isActionColumn ? 180 : (index === 0 ? 220 : 140),
        flex: isActionColumn ? 1 : (index === 0 ? 1.6 : 1),
        pinned: isActionColumn ? "right" : null,
        cellRenderer: htmlCellRenderer,
        getQuickFilterText: function (params) {
          return params.data[quickField] || "";
        }
      };
    });

    var rowData = bodyRows.map(function (row) {
      var item = {};
      Array.prototype.slice.call(row.children).forEach(function (cell, index) {
        item["col_" + index] = cell.innerHTML;
        item["__text_" + index] = textFromHtml(cell.innerHTML);
      });
      return item;
    });

    var host = document.createElement("div");
    host.className = "pct-ag-grid-host";
    host.style.width = "100%";
    var domLayout = resolveDomLayout();
    if (domLayout === "normal") {
      host.style.height = "100%";
    }
    table.parentNode.insertBefore(host, table);
    table.hidden = true;
    table.dataset.agGridMounted = "true";

    // Z7.2: Use autoHeight when skip rows present to show inline form
    var hasSkipRows = skipRows.length > 0;

    var grid = createGrid(host, {
      columnDefs: columnDefs,
      rowData: rowData,
      defaultColDef: {
        sortable: true,
        filter: true,
        floatingFilter: true,  // Z7.1: text input fields instead of icon buttons
        resizable: true,
        suppressHeaderMenuButton: true,
        suppressHeaderFilterButton: true  // Z2: no-font theme doesn't have icons
      },
      animateRows: false,
      domLayout: hasSkipRows ? "autoHeight" : domLayout,  // Z7.2: shrink if skip rows follow
      enableCellTextSelection: true,
      ensureDomOrder: true,
      suppressCellFocus: false
    });

    // Z3: Wrap skip rows in <table> to ensure <tr> elements render correctly
    if (skipRows.length > 0) {
      var wrapper = document.createElement("table");
      wrapper.className = "staff-grid pct-skip-row-wrapper";
      wrapper.style.width = "100%";
      var wrapperBody = document.createElement("tbody");
      wrapper.appendChild(wrapperBody);
      skipRows.forEach(function (row) {
        wrapperBody.appendChild(row);
      });
      host.parentNode.insertBefore(wrapper, host.nextSibling);
    }

    return grid;
  }

  function bootstrapTables() {
    var tables = document.querySelectorAll("table[data-ag-grid-auto='true']");
    tables.forEach(function (table) {
      tableToGrid(table);
    });
  }

  window.PCTAgGrid = {
    available: true,
    createGrid: createGrid,
    bootstrapTables: bootstrapTables,
    tableToGrid: tableToGrid,
    textFromHtml: textFromHtml,
    version: agGrid.VERSION || null,
  };

  document.addEventListener("DOMContentLoaded", bootstrapTables);
})();
