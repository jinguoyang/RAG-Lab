import { useState } from "react";

interface Option {
  label: string;
  text: string;
}

interface ChoiceQuestionProps {
  question: string;
  options: Option[];
  onAnswer: (answer: string) => void;
  disabled?: boolean;
}

export function ChoiceQuestion({ question, options, onAnswer, disabled }: ChoiceQuestionProps) {
  const [selected, setSelected] = useState<string | null>(null);

  function handleSelect(label: string) {
    if (disabled) return;
    setSelected(label);
    onAnswer(label);
  }

  return (
    <div className="border rounded-lg p-4 bg-blue-50">
      <p className="font-medium mb-3">{question}</p>
      <div className="grid grid-cols-2 gap-2">
        {options.map((opt) => (
          <button
            key={opt.label}
            onClick={() => handleSelect(opt.label)}
            disabled={disabled}
            className={`p-3 rounded border text-left transition-colors ${
              selected === opt.label
                ? "bg-blue-600 text-white border-blue-600"
                : "bg-white hover:bg-blue-100 border-gray-300"
            } ${disabled ? "opacity-50 cursor-not-allowed" : "cursor-pointer"}`}
          >
            <span className="font-bold mr-2">{opt.label}.</span>
            {opt.text}
          </button>
        ))}
      </div>
    </div>
  );
}
