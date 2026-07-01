export const VALID_TOPICS = [
  "politics", "military", "technology", "health",
  "science", "business", "sports", "culture", "environment",
] as const;

export const TOPIC_LABELS: Record<string, string> = {
  politics: "Политика",
  military: "Военное дело",
  technology: "Технологии",
  health: "Здоровье",
  science: "Наука",
  business: "Бизнес",
  sports: "Спорт",
  culture: "Культура",
  environment: "Экология",
};

export const TOPIC_COLORS: Record<string, string> = {
  politics: "#e05252", military: "#c0392b", technology: "#5b8dee",
  health: "#4caf7d", science: "#9b59b6", business: "#e79b47",
  sports: "#1abc9c", culture: "#f39c12", environment: "#27ae60",
};
