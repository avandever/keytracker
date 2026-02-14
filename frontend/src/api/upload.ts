import apiClient from './client';

export async function uploadLog(log: string, date?: string): Promise<{ success: boolean; crucible_game_id: string }> {
  const { data } = await apiClient.post('/upload/log', { log, date });
  return data;
}

export async function uploadSimple(gameData: Record<string, string>): Promise<{ success: boolean; crucible_game_id: string }> {
  const { data } = await apiClient.post('/upload/simple', gameData);
  return data;
}

export async function uploadCsvPods(file: File, maxDecks: number = 1000): Promise<unknown> {
  const formData = new FormData();
  formData.append('decks_csv', file);
  formData.append('max_decks', maxDecks.toString());
  formData.append('result_type', 'json');
  const { data } = await apiClient.post('/csv/pods', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return data;
}
