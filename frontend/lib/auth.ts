import { ApiError, logIn, signUp } from "./api";
import type { User } from "./types";

/**
 * 名前を入れて入室する。
 *
 * 初めての人も再訪の人も同じ操作で入れるよう、まず login を試し、
 * その名前がまだ無ければ signup する。
 */
export async function enter(name: string): Promise<User> {
  try {
    return await logIn(name);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) {
      return await signUp(name);
    }
    throw error;
  }
}
