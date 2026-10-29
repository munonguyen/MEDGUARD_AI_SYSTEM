import assert from 'node:assert/strict';
import { randomUUID } from 'node:crypto';
let cookies;
// Exercise real authentication; reuse the session across isolated test contexts.
export async function authenticatePage(page, baseUrl) {
  if (!cookies) {
    const credentials = {email:`ui-${randomUUID()}@example.com`,password:'synthetic UI password 27!'};
    const registration = await page.request.post(`${baseUrl}/v1/auth/register`, {data:{...credentials,consent:true}});
    assert.equal(registration.status(), 201, await registration.text());
    const login = await page.request.post(`${baseUrl}/v1/auth/login`, {data:credentials});
    assert.equal(login.status(), 200, await login.text());
    cookies = await page.context().cookies();
  } else await page.context().addCookies(cookies);
}
