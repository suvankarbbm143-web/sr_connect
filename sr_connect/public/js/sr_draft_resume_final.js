/* SR DRAFT RESUME EXTERNAL V1 */
(function () {
  "use strict";

  if (window.__SR_DRAFT_RESUME_EXTERNAL_V1) {
    return;
  }

  window.__SR_DRAFT_RESUME_EXTERNAL_V1 = true;
  window.srDraftResumeV1Name = "";

  function txt(value) {
    return String(value == null ? "" : value).trim();
  }

  function detail() {
    return window.srSEV3 && window.srSEV3.detail
      ? window.srSEV3.detail
      : null;
  }

  async function getDraft(workOrderId) {
    var result = await api(
      "/api/method/sr_connect.www.home.sr_stock_entry_draft_for_work_order_v1" +
        "?work_order_id=" +
        encodeURIComponent(workOrderId)
    );

    if (!result || !result.success) {
      return null;
    }

    return result.draft || null;
  }

  function setSelect(select, value) {
    value = txt(value);

    if (!select || !value) {
      return;
    }

    select.value = value;

    if (select.value !== value) {
      var option = document.createElement("option");
      option.value = value;
      option.textContent = value;
      select.appendChild(option);
      select.value = value;
    }
  }

  function setQty(input, value) {
    if (!input) {
      return;
    }

    input.value = String(Number(value || 0));

    input.dispatchEvent(
      new Event("input", { bubbles: true })
    );

    input.dispatchEvent(
      new Event("change", { bubbles: true })
    );
  }

  function rowsForMaterial(detailRow, draftItems) {
    var code1 = txt(
      detailRow &&
        (detailRow.original_item_code || detailRow.item_code)
    );

    var code2 = txt(
      detailRow &&
        (detailRow.selected_item_code || detailRow.item_code)
    );

    return draftItems.filter(function (row) {
      var code = txt(row.item_code);
      return code === code1 || code === code2;
    });
  }

  function addBatch(area) {
    var button = Array.from(
      area.querySelectorAll("button")
    ).find(function (btn) {
      return txt(btn.textContent) === "+ Add Batch";
    });

    if (!button) {
      return false;
    }

    button.click();
    return true;
  }

  function restoreDraft(detailData, draft) {
    if (
      !detailData ||
      !Array.isArray(detailData.materials) ||
      !draft ||
      !Array.isArray(draft.items)
    ) {
      return;
    }

    var areas = Array.from(
      document.querySelectorAll(
        '[data-sr-v13-area="1"]'
      )
    );

    detailData.materials.forEach(function (row, index) {
      var draftRows = rowsForMaterial(
        row,
        draft.items
      );

      if (!draftRows.length) {
        return;
      }

      var area = areas[index];

      if (!area) {
        return;
      }

      var list = area.querySelector(
        '[data-sr-v13-list="1"]'
      );

      if (!list) {
        return;
      }

      while (
        list.children.length <
        draftRows.length
      ) {
        if (!addBatch(area)) {
          break;
        }
      }

      Array.from(list.children).forEach(
        function (scope, rowIndex) {
          var saved = draftRows[rowIndex];

          if (!saved) {
            return;
          }

          var warehouse = scope.querySelector(
            '[data-sr-role="warehouse"]'
          );

          var batch = scope.querySelector(
            '[data-sr-v13-batch="1"]'
          );

          var qty = scope.querySelector(
            '[data-sr-v13-qty="1"]'
          );

          if (
            warehouse &&
            txt(saved.s_warehouse)
          ) {
            setSelect(
              warehouse,
              saved.s_warehouse
            );

            warehouse.dispatchEvent(
              new Event(
                "change",
                { bubbles: true }
              )
            );

            batch = scope.querySelector(
              '[data-sr-v13-batch="1"]'
            );
          }

          if (
            batch &&
            txt(saved.batch_no)
          ) {
            setSelect(
              batch,
              saved.batch_no
            );

            batch.dispatchEvent(
              new Event(
                "change",
                { bubbles: true }
              )
            );
          }

          if (qty) {
            setQty(
              qty,
              saved.qty
            );
          }
        }
      );
    });
  }

  function showDraftCard(draft) {
    var old = document.querySelector(
      '[data-sr-draft-resume-card="1"]'
    );

    if (old) {
      old.remove();
    }

    var firstArea = document.querySelector(
      '[data-sr-v13-area="1"]'
    );

    if (!firstArea || !draft) {
      return;
    }

    var card = document.createElement("div");

    card.setAttribute(
      "data-sr-draft-resume-card",
      "1"
    );

    card.style.cssText =
      "margin:0 0 14px 0;" +
      "padding:14px;" +
      "border:1px solid #f2d27b;" +
      "border-radius:14px;" +
      "background:#fffaf0;";

    card.innerHTML =
      '<div style="display:flex;justify-content:space-between;align-items:center;gap:12px;">' +
        '<div>' +
          '<div style="font-size:10px;font-weight:800;color:#a16207;letter-spacing:.08em;">DRAFT / IN PROGRESS</div>' +
          '<div style="font-size:14px;font-weight:800;margin-top:4px;color:#111827;">Draft: ' +
            txt(draft.name) +
          '</div>' +
          '<div style="font-size:10px;color:#78716c;margin-top:3px;">Saved in ERPNext. Continue from this Draft.</div>' +
        '</div>' +
        '<div style="padding:5px 9px;border-radius:999px;font-size:9px;font-weight:800;background:#fef3c7;color:#92400e;">DRAFT</div>' +
      '</div>';

    firstArea.parentNode.insertBefore(
      card,
      firstArea
    );
  }

  function setSubmitMode(draftName) {
    draftName = txt(draftName);

    if (!draftName) {
      return;
    }

    window.srDraftResumeV1Name =
      draftName;

    window.srSaveSubmitFinalState =
      window.srSaveSubmitFinalState || {};

    window.srSaveSubmitFinalState.stockEntry =
      draftName;

    window.srSaveSubmitFinalState.mode =
      "submit_draft";

    var button = document.getElementById(
      "srV13SaveSubmit"
    );

    if (button) {
      button.textContent = "SUBMIT";
    }
  }

  async function applyDraft(workOrderId, attempt) {
    attempt = Number(attempt || 0);

    if (!workOrderId || attempt > 12) {
      return;
    }

    var detailData = detail();

    var areas = document.querySelectorAll(
      '[data-sr-v13-area="1"]'
    );

    if (!detailData || !areas.length) {
      setTimeout(function () {
        applyDraft(
          workOrderId,
          attempt + 1
        );
      }, 150);
      return;
    }

    var draft = null;

    try {
      draft = await getDraft(
        workOrderId
      );
    } catch (error) {
      console.error(
        "SR DRAFT LOOKUP ERROR:",
        error
      );
      return;
    }

    if (!draft) {
      window.srDraftResumeV1Name = "";
      var old = document.querySelector(
        '[data-sr-draft-resume-card="1"]'
      );
      if (old) {
        old.remove();
      }
      return;
    }

    showDraftCard(draft);
    restoreDraft(
      detailData,
      draft
    );
    setSubmitMode(draft.name);
  }

  var originalOpenDetail =
    window.srSEV3OpenDetail;

  if (
    typeof originalOpenDetail ===
    "function"
  ) {
    window.srSEV3OpenDetail =
      async function () {
        var args = arguments;

        var workOrderId = txt(
          args[0] ||
            (
              detail() &&
              detail().work_order
            ) ||
            ""
        );

        var result =
          await originalOpenDetail.apply(
            this,
            args
          );

        if (workOrderId) {
          setTimeout(function () {
            applyDraft(
              workOrderId,
              0
            );
          }, 250);
        }

        return result;
      };
  }

  var originalSubmit =
    window.srSaveThenSubmitFinalV1;

  window.srSaveThenSubmitFinalV1 =
    async function () {
      var button = document.getElementById(
        "srV13SaveSubmit"
      );

      var buttonText = txt(
        button &&
        button.textContent
      ).toUpperCase();

      var draftName = txt(
        window.srDraftResumeV1Name
      );

      if (!draftName) {
        var state =
          window.srSaveSubmitFinalState ||
          {};

        draftName = txt(
          state.stockEntry
        );
      }

      if (
        buttonText === "SUBMIT" &&
        draftName
      ) {
        try {
          if (button) {
            button.disabled = true;
            button.textContent =
              "SUBMITTING...";
          }

          var result = await api(
            "/api/method/sr_connect.www.home.submit_stock_entry_from_work_order_multi_batch_final",
            {
              method: "POST",
              body: JSON.stringify({
                stock_entry_name:
                  draftName
              })
            }
          );

          if (
            !result ||
            !result.success
          ) {
            throw new Error(
              (
                result &&
                (
                  result.error ||
                  result.message
                )
              ) ||
              "Draft submit failed."
            );
          }

          window.srDraftResumeV1Name =
            "";

          if (
            window.srSaveSubmitFinalState
          ) {
            window.srSaveSubmitFinalState.stockEntry =
              "";

            window.srSaveSubmitFinalState.mode =
              "submitted";
          }

          alert("Submit done");
          return result;
        } catch (error) {
          console.error(
            "SR DRAFT SUBMIT ERROR:",
            error
          );

          alert(
            error && error.message
              ? error.message
              : "Draft submit failed."
          );

          return;
        } finally {
          if (button) {
            button.disabled = false;
          }
        }
      }

      if (
        typeof originalSubmit ===
        "function"
      ) {
        return originalSubmit.apply(
          this,
          arguments
        );
      }
    };

  setTimeout(function () {
    var detailData = detail();

    var workOrderId = txt(
      detailData &&
        detailData.work_order
    );

    if (workOrderId) {
      applyDraft(
        workOrderId,
        0
      );
    }
  }, 800);
})();
