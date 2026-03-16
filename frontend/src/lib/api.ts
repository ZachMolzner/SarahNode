export async function enqueueMockMessage(username: string, content: string): Promise<void> {
  await fetch(`http://localhost:8000/api/mock-chat/simple?username=${encodeURIComponent(username)}&content=${encodeURIComponent(content)}`, {
    method: 'POST',
  });
}
