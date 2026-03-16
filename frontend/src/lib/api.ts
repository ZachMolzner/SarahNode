const API_BASE_URL = 'http://localhost:8000';

export async function sendSimpleMockChat(
  username: string,
  content: string,
  priority = 1,
): Promise<void> {
  const params = new URLSearchParams({ username, content, priority: String(priority) });
  const response = await fetch(`${API_BASE_URL}/api/mock-chat/simple?${params.toString()}`, {
    method: 'POST',
  });

  if (!response.ok) {
    throw new Error(`Failed to queue message: ${response.status}`);
  }
}
