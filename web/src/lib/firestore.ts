import { doc, getDoc, setDoc } from "firebase/firestore";
import { getFirebaseDb } from "./firebase";
import { UserCollection } from "./types";

export async function getUserCollection(userId: string): Promise<UserCollection> {
  const ref = doc(getFirebaseDb(), "users", userId);
  const snap = await getDoc(ref);
  if (snap.exists()) {
    return (snap.data().collection || {}) as UserCollection;
  }
  return {};
}

export async function saveUserCollection(
  userId: string,
  collection: UserCollection
): Promise<void> {
  const ref = doc(getFirebaseDb(), "users", userId);
  await setDoc(ref, { collection }, { merge: true });
}
