import { beforeEach, describe, expect, it } from "vitest";

import { storage } from "../../frontend/src/utils/storage";

const bucket = new Map<string, string>();

beforeEach(() => {
  bucket.clear();
  Object.defineProperty(globalThis, "localStorage", {
    value: {
      getItem: (key: string) => bucket.get(key) ?? null,
      setItem: (key: string, value: string) => bucket.set(key, value),
      removeItem: (key: string) => bucket.delete(key),
    },
    configurable: true,
  });
});

describe("storage helper", () => {
  it("stores token", () => {
    storage.setToken("abc");
    expect(storage.getToken()).toBe("abc");
    storage.clearToken();
    expect(storage.getToken()).toBe("");
  });
});
