window.PCTTabulator = {
  version: "1.0.0",

  create: function(hostId, options) {
    var host = document.getElementById(hostId);
    if (!host) return null;

    // Defaults
    var columns = (options.columns || []).map(function(col) {
      var base = {
        title: col.title || "",
        field: col.field,
        widthGrow: col.widthGrow || 1,
        minWidth: col.minWidth || 120,
        formatter: "html",          // все ячейки — HTML
        headerFilter: "input",      // фильтр под заголовком
        headerFilterPlaceholder: "",
        resizable: true,
      };

      // Action / Open columns
      if (col.frozen) {
        base.frozen = true;
        base.headerFilter = false;
        base.headerSort = false;
        base.width = col.width || 180;
        base.widthGrow = 0;
        base.hozAlign = "center";
      }

      // First column wider
      if (col.widthGrow === 1.6) {
        base.minWidth = 220;
      }

      // Override from options
      if (col.headerFilter === false) base.headerFilter = false;
      if (col.headerSort === false) base.headerSort = false;
      if (col.width) base.width = col.width;
      if (col.hozAlign) base.hozAlign = col.hozAlign;
      if (col.formatter) base.formatter = col.formatter;

      return base;
    });

    var isMobile = window.innerWidth <= 768;

    return new Tabulator(host, {
      data: options.data || [],
      columns: columns,
      layout: "fitColumns",
      height: isMobile ? undefined : "100%",
      movableColumns: false,
      placeholder: "Нет данных",
      headerSortElement: function(column, dir) {
        return dir === "asc" ? " ↑" : dir === "desc" ? " ↓" : "";
      },
      selectableRows: false,
    });
  }
};
