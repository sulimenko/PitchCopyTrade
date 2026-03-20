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

  function tableToGrid(table) {
    if (!table || table.dataset.agGridMounted === "true") {
      return null;
    }

    var headers = Array.prototype.slice.call(table.querySelectorAll("thead th"));
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
    table.parentNode.insertBefore(host, table);
    table.hidden = true;
    table.dataset.agGridMounted = "true";

    return createGrid(host, {
      columnDefs: columnDefs,
      rowData: rowData,
      defaultColDef: {
        sortable: true,
        filter: true,
        resizable: true,
        suppressHeaderMenuButton: true
      },
      animateRows: false,
      domLayout: "autoHeight",
      enableCellTextSelection: true,
      ensureDomOrder: true,
      suppressCellFocus: false
    });
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
