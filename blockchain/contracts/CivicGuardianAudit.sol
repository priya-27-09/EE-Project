// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

/**
 * @title CivicGuardianAudit
 * @dev Tamper-evident, immutable audit registry for civic grievance lifecycle events.
 * Stored records contain cryptographic hashes (SHA-256) and non-sensitive metadata only.
 * No PII, passwords, JWT tokens, images, or GPS coordinates are stored on-chain.
 */
contract CivicGuardianAudit {
    address public owner;
    address public authorizedWriter;

    struct AuditRecord {
        bytes32 dataHash;
        bytes32 eventHash;
        uint256 timestamp;
        string eventType;
        string complaintReference;
    }

    // Mapping from unique eventHash -> AuditRecord
    mapping(bytes32 => AuditRecord) private records;

    // Track list of all recorded event hashes for enumerable auditing if needed
    bytes32[] private recordedEventHashes;

    event AuditRecorded(
        bytes32 indexed eventHash,
        bytes32 indexed dataHash,
        string eventType,
        uint256 timestamp
    );

    event AuthorizedWriterUpdated(
        address indexed previousWriter,
        address indexed newWriter
    );

    modifier onlyAuthorized() {
        require(
            msg.sender == owner || msg.sender == authorizedWriter,
            "CivicGuardianAudit: caller is not authorized writer"
        );
        _;
    }

    modifier onlyOwner() {
        require(msg.sender == owner, "CivicGuardianAudit: caller is not contract owner");
        _;
    }

    constructor() {
        owner = msg.sender;
        authorizedWriter = msg.sender;
    }

    /**
     * @dev Update the authorized backend signer address.
     * @param _writer The new address authorized to anchor audit records.
     */
    function setAuthorizedWriter(address _writer) external onlyOwner {
        require(_writer != address(0), "CivicGuardianAudit: invalid writer address");
        address prev = authorizedWriter;
        authorizedWriter = _writer;
        emit AuthorizedWriterUpdated(prev, _writer);
    }

    /**
     * @dev Anchors an immutable audit event on-chain.
     * @param dataHash SHA-256 hash of the canonical event payload.
     * @param eventHash Unique deterministic hash identifying this event instance.
     * @param eventType Category of event (e.g. COMPLAINT_CREATED, RESOLUTION_VERIFICATION).
     * @param complaintReference Non-sensitive public complaint reference (e.g. CG-2026-000001).
     */
    function recordAudit(
        bytes32 dataHash,
        bytes32 eventHash,
        string calldata eventType,
        string calldata complaintReference
    ) external onlyAuthorized {
        require(eventHash != bytes32(0), "CivicGuardianAudit: eventHash cannot be empty");
        require(dataHash != bytes32(0), "CivicGuardianAudit: dataHash cannot be empty");
        require(records[eventHash].timestamp == 0, "CivicGuardianAudit: record already exists for eventHash");

        records[eventHash] = AuditRecord({
            dataHash: dataHash,
            eventHash: eventHash,
            timestamp: block.timestamp,
            eventType: eventType,
            complaintReference: complaintReference
        });

        recordedEventHashes.push(eventHash);

        emit AuditRecorded(eventHash, dataHash, eventType, block.timestamp);
    }

    /**
     * @dev Retrieves an anchored audit record by its unique eventHash.
     */
    function getAudit(bytes32 eventHash) external view returns (
        bytes32 dataHash,
        bytes32 recordedEventHash,
        uint256 timestamp,
        string memory eventType,
        string memory complaintReference
    ) {
        AuditRecord memory rec = records[eventHash];
        require(rec.timestamp > 0, "CivicGuardianAudit: record not found");
        return (
            rec.dataHash,
            rec.eventHash,
            rec.timestamp,
            rec.eventType,
            rec.complaintReference
        );
    }

    /**
     * @dev Cryptographically verifies whether a given dataHash matches the on-chain record.
     * Returns true only when the record exists and dataHash strictly matches.
     */
    function verifyAudit(bytes32 eventHash, bytes32 dataHash) external view returns (bool) {
        AuditRecord memory rec = records[eventHash];
        if (rec.timestamp == 0) {
            return false;
        }
        return rec.dataHash == dataHash;
    }

    /**
     * @dev Returns total number of anchored audit records.
     */
    function totalRecords() external view returns (uint256) {
        return recordedEventHashes.length;
    }
}
