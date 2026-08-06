(function (root) {
  "use strict";

  function parseBatchSizes(value) {
    var raw = String(value == null ? "" : value).trim();
    if (!raw) {
      return { ok: false, error: "empty" };
    }

    var tokens = raw.split(",");
    var sizes = [];
    var total = 0;

    for (var i = 0; i < tokens.length; i++) {
      var token = tokens[i].trim();
      if (!/^[1-9]\d*$/.test(token)) {
        return { ok: false, error: "invalid" };
      }

      var size = Number(token);
      if (!Number.isSafeInteger(size)) {
        return { ok: false, error: "invalid" };
      }
      sizes.push(size);
      total += size;

      if (!Number.isSafeInteger(total)) {
        return { ok: false, error: "invalid" };
      }
    }

    return { ok: true, sizes: sizes, total: total };
  }

  function batchSizesFromTypes(types) {
    var sizes = [];
    var currentSize = null;

    for (var i = 0; i < types.length; i++) {
      if (types[i] === "S") {
        if (currentSize !== null) {
          return [];
        }
        currentSize = 0;
      } else if (types[i] === "C") {
        if (currentSize === null) {
          return [];
        }
        currentSize += 1;
      } else if (types[i] === "E") {
        if (currentSize === null || currentSize === 0) {
          return [];
        }
        sizes.push(currentSize);
        currentSize = null;
      } else {
        return [];
      }
    }

    return currentSize === null ? sizes : [];
  }

  function createController(options) {
    var $ = options.$;
    var $rows = options.$table.find("tbody:first");
    var $input = options.$input;
    var $status = options.$status;

    function rowIsDeleted($row) {
      var $delete = $row.find("input[id$=DELETE]");
      return $delete.length && $delete.is(":checked");
    }

    function rowsOfType(type) {
      return $rows.children("tr").filter(function () {
        var $row = $(this);
        return $row.attr("data-type") === type && !rowIsDeleted($row);
      });
    }

    function setStatus(message, isError) {
      $status
        .toggleClass("batch-split-error", !!isError)
        .toggleClass("batch-split-success", !isError && !!message)
        .text(message);
    }

    function formatMessage(message, values) {
      return Object.keys(values).reduce(function (result, key) {
        return result.replace("{" + key + "}", values[key]);
      }, message);
    }

    function addCaseRow() {
      var previousTotal = parseInt(options.$total.val(), 10);
      options.addRow();
      if (parseInt(options.$total.val(), 10) === previousTotal) {
        return $();
      }
      return $rows.children("tr").last();
    }

    function markerRows(type) {
      return $rows
        .children("tr")
        .filter(function () {
          var $row = $(this);
          return (
            $row.attr("data-type") === type &&
            (!rowIsDeleted($row) || $row.attr("data-batch-split-unused") === "true")
          );
        })
        .toArray();
    }

    function defaultBatchPoints($batchRows) {
      var points = 0;
      $batchRows.each(function () {
        var value = $(this).find("input[id$=points]").val();
        var parsed = Number(value);
        if (value !== "" && Number.isFinite(parsed)) {
          points += parsed;
        }
      });
      return points > 0 ? points : $batchRows.length;
    }

    function pretestValue($row) {
      var $field = $row.find("input[id$=pretest]");
      if (!$field.length) {
        return false;
      }
      if ($field.is(":checkbox")) {
        return $field.is(":checked");
      }
      return /^(1|on|true|yes)$/i.test($field.val() || "");
    }

    function setPretestValue($row, value) {
      var $field = $row.find("input[id$=pretest]");
      if ($field.is(":checkbox")) {
        $field.prop("checked", value).change();
      } else {
        $field.val(value ? "True" : "False").change();
      }
    }

    function batchPretestState($batchRows) {
      var hasPretests = false;
      var hasRegularTests = false;
      $batchRows.each(function () {
        var isPretest = pretestValue($(this));
        hasPretests = hasPretests || isPretest;
        hasRegularTests = hasRegularTests || !isPretest;
      });
      return {
        mixed: hasPretests && hasRegularTests,
        value: hasPretests,
      };
    }

    function clearMarkerCaseFields($row) {
      $row.find("select[id$=input_file], select[id$=output_file]").val(null).change();
      $row.find("input[id$=generator_args]").val("").change();
    }

    function activateMarker($row, type, $batchRows) {
      var previousType = $row.attr("data-type");
      $row.removeAttr("data-batch-split-unused").show();
      $row.find("input[id$=DELETE]").prop("checked", false).change();
      $row.find("select[id$=type]").val(type).change();

      if (type === "S") {
        if (previousType !== "S") {
          clearMarkerCaseFields($row);
          $row.find("select[id$=batch_scoring]").val("sum").change();
        }
        var $points = $row.find("input[id$=points]");
        if (previousType !== "S" || $points.val() === "") {
          $points.val(defaultBatchPoints($batchRows)).change();
        }
        setPretestValue($row, batchPretestState($batchRows).value);
      } else {
        clearMarkerCaseFields($row);
        $row.find("input[id$=points]").val("").change();
      }
    }

    function markMarkerUnused($row) {
      $row.attr("data-batch-split-unused", "true").hide();
      $row.find("input[id$=DELETE]").prop("checked", true).change();
    }

    function setRowOrder($row, value) {
      var $order = $row.find("input[id$=order]");
      $order.val(value).change();
      $order.siblings("span.order").text(value);
    }

    function apply() {
      setStatus("", false);

      var parsed = parseBatchSizes($input.val());
      if (!parsed.ok) {
        setStatus(
          parsed.error === "empty" ? options.messages.empty : options.messages.invalid,
          true,
        );
        return false;
      }

      var hasPendingDeletes =
        $rows.children("tr").filter(function () {
          var $row = $(this);
          return rowIsDeleted($row) && $row.attr("data-batch-split-unused") !== "true";
        }).length > 0;
      if (hasPendingDeletes) {
        setStatus(options.messages.pendingDeletes, true);
        return false;
      }

      var normalRows = rowsOfType("C").toArray();
      if (parsed.total !== normalRows.length) {
        setStatus(
          formatMessage(options.messages.countMismatch, {
            expected: parsed.total,
            actual: normalRows.length,
          }),
          true,
        );
        return false;
      }

      var groupedRows = [];
      var groupOffset = 0;
      for (var groupIndex = 0; groupIndex < parsed.sizes.length; groupIndex++) {
        var group = normalRows.slice(groupOffset, groupOffset + parsed.sizes[groupIndex]);
        if (batchPretestState($(group)).mixed) {
          setStatus(formatMessage(options.messages.mixedPretests, { batch: groupIndex + 1 }), true);
          return false;
        }
        groupedRows.push(group);
        groupOffset += parsed.sizes[groupIndex];
      }

      var starts = markerRows("S");
      var ends = markerRows("E");
      var desiredStarts = starts.splice(0, parsed.sizes.length);
      var desiredEnds = ends.splice(0, parsed.sizes.length);

      while (desiredStarts.length < parsed.sizes.length && ends.length) {
        desiredStarts.push(ends.shift());
      }
      while (desiredEnds.length < parsed.sizes.length && starts.length) {
        desiredEnds.push(starts.shift());
      }

      var missingMarkers = parsed.sizes.length * 2 - desiredStarts.length - desiredEnds.length;
      var requiredRows = parseInt(options.$total.val(), 10) + missingMarkers;
      if (requiredRows > options.testcaseLimit) {
        setStatus(
          formatMessage(options.messages.limitExceeded, {
            rows: requiredRows,
            limit: options.testcaseLimit,
          }),
          true,
        );
        return false;
      }

      while (desiredStarts.length < parsed.sizes.length) {
        var $start = addCaseRow();
        if (!$start.length) {
          return false;
        }
        desiredStarts.push($start.get(0));
      }
      while (desiredEnds.length < parsed.sizes.length) {
        var $end = addCaseRow();
        if (!$end.length) {
          return false;
        }
        desiredEnds.push($end.get(0));
      }

      var orderedRows = [];
      for (var batchIndex = 0; batchIndex < parsed.sizes.length; batchIndex++) {
        var batchRows = groupedRows[batchIndex];
        var $batchRows = $(batchRows);
        var $startRow = $(desiredStarts[batchIndex]);
        var $endRow = $(desiredEnds[batchIndex]);

        activateMarker($startRow, "S", $batchRows);
        activateMarker($endRow, "E", $batchRows);
        orderedRows.push($startRow.get(0));
        Array.prototype.push.apply(orderedRows, batchRows);
        orderedRows.push($endRow.get(0));
      }

      starts.concat(ends).forEach(function (row) {
        markMarkerUnused($(row));
      });

      orderedRows.forEach(function (row, index) {
        var $row = $(row);
        $rows.append($row);
        setRowOrder($row, index + 1);
      });
      starts.concat(ends).forEach(function (row) {
        $rows.append(row);
      });

      $input.val(parsed.sizes.join(", "));
      options.handleTableReorder();
      setStatus(
        formatMessage(options.messages.success, {
          tests: parsed.total,
          batches: parsed.sizes.length,
        }),
        false,
      );
      return true;
    }

    function fillFromTable() {
      var types = $rows
        .children("tr")
        .filter(function () {
          return !rowIsDeleted($(this));
        })
        .map(function () {
          return $(this).attr("data-type");
        })
        .get();
      var sizes = batchSizesFromTypes(types);
      if (sizes.length) {
        $input.val(sizes.join(", "));
      }
    }

    function bind() {
      options.$applyButton.click(apply);
      $input.on("input", function () {
        setStatus("", false);
      });
      $input.keydown(function (event) {
        if (event.key === "Enter") {
          event.preventDefault();
          apply();
        }
      });
      fillFromTable();
    }

    return {
      addCaseRow: addCaseRow,
      apply: apply,
      bind: bind,
      rowsOfType: rowsOfType,
    };
  }

  root.VKOJProblemDataBatch = {
    parseBatchSizes: parseBatchSizes,
    batchSizesFromTypes: batchSizesFromTypes,
    createController: createController,
  };
})(typeof window === "undefined" ? globalThis : window);
