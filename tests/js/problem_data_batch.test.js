import assert from "node:assert/strict";
import test from "node:test";

await import("../../resources/problem_data_batch.js");

const batchTools = globalThis.VKOJProblemDataBatch;

test("parses comma-separated positive batch sizes", () => {
  assert.deepEqual(batchTools.parseBatchSizes("8, 10,10, 12"), {
    ok: true,
    sizes: [8, 10, 10, 12],
    total: 40,
  });
});

test("rejects empty or invalid batch sizes", () => {
  for (const value of ["", "0", "-1", "1.5", "1,,2", "abc", "999999999999999999999"]) {
    assert.equal(batchTools.parseBatchSizes(value).ok, false, value);
  }
});

test("derives batch sizes from complete batch markers", () => {
  assert.deepEqual(batchTools.batchSizesFromTypes(["S", "C", "C", "E", "S", "C", "E"]), [2, 1]);
});

test("does not derive sizes from standalone or incomplete rows", () => {
  assert.deepEqual(batchTools.batchSizesFromTypes(["C"]), []);
  assert.deepEqual(batchTools.batchSizesFromTypes(["S", "C"]), []);
  assert.deepEqual(batchTools.batchSizesFromTypes(["S", "E"]), []);
});
