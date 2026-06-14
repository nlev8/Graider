import React from "react";
import Icon from "../../components/Icon";

/*
 * AccommodationModalFooter — extracted from AccommodationModal (CQ wave-8 split,
 * #cq8-05). Contains the ELL language selector (shown only when the ell_support
 * preset is selected), the custom notes textarea, and the Save / Cancel action
 * buttons.
 *
 * Pure-prop component: no state, no effects, no fetches. All state and handlers
 * are owned by AccommodationModal and passed down as props.
 */
export default function AccommodationModalFooter({
  selectedAccommodationPresets,
  accommEllLanguage,
  setAccommEllLanguage,
  accommodationCustomNotes,
  setAccommodationCustomNotes,
  onSave,
  onCancel,
}) {
  return (
    <>
      {/* ELL Language selector — shown when ELL Support preset is selected */}
      {selectedAccommodationPresets.includes("ell_support") && (
        <div style={{ marginBottom: "20px" }}>
          <label className="label">
            Home Language (for bilingual feedback)
          </label>
          <select
            className="input"
            value={accommEllLanguage}
            onChange={(e) => setAccommEllLanguage(e.target.value)}
          >
            <option value="">English only (no translation)</option>
            <option value="spanish">Spanish</option>
            <option value="portuguese">Portuguese</option>
            <option value="haitian creole">Haitian Creole</option>
            <option value="french">French</option>
            <option value="arabic">Arabic</option>
            <option value="chinese (simplified)">Chinese (Simplified)</option>
            <option value="chinese (traditional)">Chinese (Traditional)</option>
            <option value="vietnamese">Vietnamese</option>
            <option value="korean">Korean</option>
            <option value="tagalog">Tagalog</option>
            <option value="russian">Russian</option>
            <option value="hindi">Hindi</option>
            <option value="urdu">Urdu</option>
            <option value="bengali">Bengali</option>
            <option value="japanese">Japanese</option>
            <option value="german">German</option>
            <option value="italian">Italian</option>
            <option value="polish">Polish</option>
            <option value="somali">Somali</option>
            <option value="swahili">Swahili</option>
            <option value="burmese">Burmese</option>
            <option value="nepali">Nepali</option>
            <option value="gujarati">Gujarati</option>
            <option value="amharic">Amharic</option>
          </select>
          <p
            style={{
              fontSize: "0.75rem",
              color: "var(--text-muted)",
              marginTop: "6px",
            }}
          >
            If set, feedback will be provided in both English and
            the selected language.
          </p>
        </div>
      )}

      {/* Custom Notes */}
      <div style={{ marginBottom: "20px" }}>
        <label className="label">
          Additional Notes (Optional)
        </label>
        <textarea
          className="input"
          value={accommodationCustomNotes}
          onChange={(e) => setAccommodationCustomNotes(e.target.value)}
          placeholder="Any additional accommodation instructions..."
          style={{ minHeight: "80px", resize: "vertical" }}
        />
        <p
          style={{
            fontSize: "0.75rem",
            color: "var(--text-muted)",
            marginTop: "6px",
          }}
        >
          These notes will be included in AI grading instructions
          (without student identity).
        </p>
      </div>

      {/* Actions */}
      <div
        style={{
          display: "flex",
          gap: "10px",
          justifyContent: "flex-end",
        }}
      >
        <button onClick={onSave} className="btn btn-primary">
          <Icon name="Save" size={18} />
          Save Accommodations
        </button>
        <button onClick={onCancel} className="btn btn-secondary">
          Cancel
        </button>
      </div>
    </>
  );
}
