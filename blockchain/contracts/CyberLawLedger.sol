pragma solidity ^0.8.0;

// You might need to import OpenZeppelin's Ownable if you want
// only the contract deployer (your backend's treasury) to call certain functions.
// For hackathon simplicity, we'll omit it for now, assuming trust in backend.
// import "@openzeppelin/contracts/access/Ownable.sol";

contract CyberLawLedger {
    // Structure to store details of each case
    struct Case {
        string caseId;              // Unique identifier for the case (from frontend)
        string postHash;            // SHA256 hash of the problematic post content
        address victimAddress;      // The wallet address of the victim for compensation
        string violationType;       // Type of violation (e.g., "Defamation", "Hate Speech")
        string councilDecision;     // Final decision by the Defi Council/Judge
        uint256 penaltyAmountWei;   // Fine amount in Wei (smallest unit of ETH/MATIC)
        string banStatus;           // Status of ban (e.g., "Permanent", "Temporary", "None")
        string decisionExplanation; // Explanation for the decision
        uint256 compensationToVictimWei; // Amount to compensate victim in Wei
        uint256 socialScore;        // New: Social score assigned to the "bad actor"
        bool fineCollected;         // True if the fine has been paid
        bool compensationDistributed; // True if compensation has been sent
        uint256 timestamp;          // Timestamp of the case recording
    }

    // Mapping to store cases by their caseId
    mapping(string => Case) public cases;
    // Array to keep track of all caseIds, useful for iterating (less efficient for many cases)
    string[] public caseIds;

    // Events to emit for external listeners (like your backend)
    event CaseRecorded(string indexed caseId, address indexed victim, uint256 penalty, uint256 compensation, uint256 socialScore);
    event FineCollected(string indexed caseId, uint256 amount);
    event CompensationDistributed(string indexed caseId, address indexed victim, uint256 amount);

    // Function to record a new case on the ledger
    // This function is typically called by your backend's authorized wallet (treasury/Judge Agent).
    // It records the intended penalty, not collects it directly.
    function recordCase(
        string memory _caseId,
        string memory _postHash,
        address _victimAddress,
        string memory _violationType,
        string memory _councilDecision,
        uint256 _penaltyAmountWei,
        string memory _banStatus,
        string memory _decisionExplanation,
        uint256 _compensationToVictimWei,
        uint256 _socialScore
    ) public { // In a real system, consider 'onlyOwner' or specific role-based access control
        require(cases[_caseId].timestamp == 0, "Case with this ID already exists."); // Ensure ID is unique

        cases[_caseId] = Case(
            _caseId,
            _postHash,
            _victimAddress,
            _violationType,
            _councilDecision,
            _penaltyAmountWei,
            _banStatus,
            _decisionExplanation,
            _compensationToVictimWei,
            _socialScore,
            false, // fineCollected
            false, // compensationDistributed
            block.timestamp // Record the timestamp of the blockchain transaction
        );
        caseIds.push(_caseId); // Add the new case ID to the public array

        emit CaseRecorded(_caseId, _victimAddress, _penaltyAmountWei, _compensationToVictimWei, _socialScore);
    }

    // Function for the "bad actor" (defendant) to pay the fine
    // This function must be `payable` to receive native cryptocurrency (ETH/MATIC).
    function payFine(string memory _caseId) public payable {
        Case storage currentCase = cases[_caseId];
        require(currentCase.timestamp != 0, "Case does not exist.");
        require(!currentCase.fineCollected, "Fine already collected for this case.");
        require(msg.value >= currentCase.penaltyAmountWei, "Sent amount is less than the required penalty.");

        // Mark the fine as collected. The funds remain in the contract.
        currentCase.fineCollected = true;

        emit FineCollected(_caseId, msg.value);
    }

    // Function for your system's treasury/Judge Agent to distribute compensation to the victim
    // This would be called by your backend's authorized wallet.
    function distributeCompensation(string memory _caseId) public { // In a real system, consider 'onlyOwner'
        Case storage currentCase = cases[_caseId];
        require(currentCase.timestamp != 0, "Case does not exist.");
        require(currentCase.fineCollected, "Fine not yet collected to distribute compensation.");
        require(!currentCase.compensationDistributed, "Compensation already distributed for this case.");
        require(address(this).balance >= currentCase.compensationToVictimWei, "Contract has insufficient balance for compensation.");

        // Transfer the compensation amount to the victim's address
        (bool success, ) = currentCase.victimAddress.call{value: currentCase.compensationToVictimWei}("");
        require(success, "Failed to send compensation to victim.");

        currentCase.compensationDistributed = true;
        emit CompensationDistributed(_caseId, currentCase.victimAddress, currentCase.compensationToVictimWei);
    }

    // Getter function to retrieve details of a specific case
    function getCase(string memory _caseId) public view returns (
        string memory caseId,
        string memory postHash,
        address victimAddress,
        string memory violationType,
        string memory councilDecision,
        uint256 penaltyAmountWei,
        string memory banStatus,
        string memory decisionExplanation,
        uint256 compensationToVictimWei,
        uint256 socialScore,
        bool fineCollected,
        bool compensationDistributed,
        uint256 timestamp
    ) {
        Case storage currentCase = cases[_caseId];
        return (
            currentCase.caseId,
            currentCase.postHash,
            currentCase.victimAddress,
            currentCase.violationType,
            currentCase.councilDecision,
            currentCase.penaltyAmountWei,
            currentCase.banStatus,
            currentCase.decisionExplanation,
            currentCase.compensationToVictimWei,
            currentCase.socialScore,
            currentCase.fineCollected,
            currentCase.compensationDistributed,
            currentCase.timestamp
        );
    }

    // Function to get all case IDs (useful for frontend to fetch all cases)
    function getAllCaseIds() public view returns (string[] memory) {
        return caseIds;
    }
}
