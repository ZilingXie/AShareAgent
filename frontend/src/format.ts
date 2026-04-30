export function money(value: string | null | undefined): string {
  if (!value) {
    return "-";
  }
  const numberValue = Number(value);
  if (Number.isNaN(numberValue)) {
    return value;
  }
  return new Intl.NumberFormat("zh-CN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  }).format(numberValue);
}

export function percent(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "-";
  }
  return `${(value * 100).toFixed(2)}%`;
}

export function days(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "-";
  }
  return `${value.toFixed(2)} 天`;
}

export function score(value: number): string {
  return value.toFixed(2);
}

export function boolText(value: boolean): "True" | "False" {
  return value ? "True" : "False";
}

export function breakdown(value: Record<string, number>): string {
  const entries = Object.entries(value);
  if (entries.length === 0) {
    return "-";
  }
  return entries.map(([key, item]) => `${key}: ${score(item)}`).join(" / ");
}

export function listText(values: string[]): string {
  if (values.length === 0) {
    return "-";
  }
  return values.join("；");
}

export function distributionText(value: Record<string, number>): string {
  const entries = Object.entries(value);
  if (entries.length === 0) {
    return "-";
  }
  return entries.map(([key, item]) => `${key}: ${item}`).join("；");
}
